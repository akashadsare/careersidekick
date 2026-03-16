"""Job extraction service for parsing job postings from URLs with ATS detection."""

import re
from datetime import datetime, UTC
from typing import Optional
import logging

try:
    import httpx
    from bs4 import BeautifulSoup
except ImportError:
    # Graceful fallback if libraries not installed
    httpx = None
    BeautifulSoup = None

logger = logging.getLogger(__name__)


class AtsDetectionResult:
    """Result of ATS detection analysis."""

    def __init__(
        self,
        ats_type: Optional[str] = None,
        confidence: float = 0.0,
        indicators: Optional[list[str]] = None
    ):
        self.ats_type = ats_type
        self.confidence = confidence
        self.indicators = indicators or []


class JobExtractor:
    """Extract job posting data from URLs with ATS type detection."""

    # ATS detection patterns: regex patterns and domain indicators per ATS type
    ATS_PATTERNS = {
        'greenhouse': {
            'domains': ['boards.greenhouse.io', 'greenhouse.io'],
            'patterns': [
                r'greenhouse',
                r'powered by greenhouse',
                r'greenhouse.io',
            ],
            'selectors': [
                '.section--description',
                '[data-department]',
                '[data-office-location]',
            ]
        },
        'lever': {
            'domains': ['lever.co', 'jobs.lever.co', 'apply.lever.co'],
            'patterns': [
                r'lever\.co',
                r'powered by lever',
                r'_LeverApplicationForm',
            ],
            'selectors': [
                '.page-full-width',
                '[data-qa="posting"]',
                '.lever-form'
            ]
        },
        'workday': {
            'domains': ['myworkdayjobs.com', 'workday.com'],
            'patterns': [
                r'workday',
                r'myworkdayjobs',
                r'powered by workday',
            ],
            'selectors': [
                '[data-automation-id]',
                '.css-i2b8tz',
                '.jobDescription'
            ]
        },
        'ashby': {
            'domains': ['jobs.ashby.ai', 'ashby.ai'],
            'patterns': [
                r'ashby',
                r'ashby\.ai',
                r'powered by ashby',
            ],
            'selectors': [
                '[data-test-id]',
                '.ashby-job-description',
                '.job-application'
            ]
        },
        'linkedin': {
            'domains': ['linkedin.com/jobs'],
            'patterns': [
                r'linkedin\.com.*jobs',
                r'linkedin jobs',
            ],
            'selectors': [
                '.description__text',
                '[data-test-id="show-more-html"]',
                '.show-more-less-html'
            ]
        }
    }

    CLOSED_JOB_INDICATORS = [
        r'job.*closed',
        r'no longer.*open',
        r'position.*filled',
        r'application.*closed',
        r'this.*job.*no longer',
        r'sorry.*job.*not.*available',
        r'this position has been filled',
    ]

    def __init__(self, timeout: int = 10):
        """Initialize extractor with optional timeout for HTTP requests."""
        self.timeout = timeout

    def extract(self, url: str) -> dict:
        """
        Extract job posting data from URL.

        Args:
            url: Full URL to job posting

        Returns:
            dict with extracted data: title, company_name, location, description,
            apply_url, ats_type, ats_detection_confidence, is_closed
        """
        result = {
            'title': None,
            'company_name': None,
            'location': None,
            'description': None,
            'apply_url': url,  # Start with provided URL
            'ats_type': None,
            'ats_detection_confidence': 0.0,
            'is_closed': False,
            'extraction_errors': []
        }

        try:
            # Detect ATS type from URL/domain first
            ats_result = self._detect_ats(url)
            result['ats_type'] = ats_result.ats_type
            result['ats_detection_confidence'] = ats_result.confidence

            # Fetch and parse page content
            if httpx is None or BeautifulSoup is None:
                logger.warning("httpx or BeautifulSoup not installed; using fallback extraction")
                return self._extract_fallback(url, result)

            try:
                html_content = self._fetch_url(url)
            except Exception as e:
                logger.error(f"Failed to fetch URL {url}: {e}")
                result['extraction_errors'].append(f"Failed to fetch page: {str(e)}")
                return result

            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract title and company
            title_data = self._extract_title_and_company(soup, ats_result.ats_type)
            result['title'] = title_data.get('title') or result['title']
            result['company_name'] = title_data.get('company_name') or result['company_name']

            # Extract location
            location = self._extract_location(soup, ats_result.ats_type)
            if location:
                result['location'] = location

            # Extract description
            description = self._extract_description(soup, ats_result.ats_type)
            if description:
                result['description'] = description

            # Check if job is closed
            is_closed = self._detect_closed_job(soup, html_content)
            result['is_closed'] = is_closed

            # Extract application URL (often different from source_url)
            apply_url = self._extract_apply_url(soup, ats_result.ats_type)
            if apply_url:
                result['apply_url'] = apply_url

        except Exception as e:
            logger.error(f"Unexpected error during extraction: {e}")
            result['extraction_errors'].append(f"Unexpected error: {str(e)}")

        return result

    def _fetch_url(self, url: str) -> str:
        """Fetch URL content with timeout and retry logic."""
        if httpx is None:
            raise RuntimeError("httpx not installed")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            return response.text

    def _detect_ats(self, url: str) -> AtsDetectionResult:
        """Detect ATS type from URL and domain patterns."""
        url_lower = url.lower()

        # Check domain-level detection (highest priority)
        for ats_type, patterns in self.ATS_PATTERNS.items():
            for domain in patterns['domains']:
                if domain in url_lower:
                    return AtsDetectionResult(
                        ats_type=ats_type,
                        confidence=0.95,  # High confidence from domain
                        indicators=[f"Domain match: {domain}"]
                    )

        return AtsDetectionResult(ats_type=None, confidence=0.0)

    def _detect_ats_from_html(self, soup, html_text: str) -> AtsDetectionResult:
        """Detect ATS type from HTML content patterns."""
        html_lower = html_text.lower()
        scores = {}

        for ats_type, patterns in self.ATS_PATTERNS.items():
            indicators = []
            total_score = 0

            # Check regex patterns
            for pattern in patterns['patterns']:
                if re.search(pattern, html_lower, re.IGNORECASE):
                    total_score += 1
                    indicators.append(f"Pattern match: {pattern}")

            # Check meta tags, scripts, attributes
            for selector in patterns['selectors']:
                try:
                    if soup.select(selector):
                        total_score += 0.5
                        indicators.append(f"CSS selector match: {selector}")
                except Exception:
                    pass

            if total_score > 0:
                scores[ats_type] = {
                    'score': total_score,
                    'indicators': indicators
                }

        if scores:
            best_ats = max(scores.items(), key=lambda x: x[1]['score'])
            ats_type = best_ats[0]
            confidence = min(best_ats[1]['score'] / 3.0, 1.0)  # Normalize to 0-1
            return AtsDetectionResult(
                ats_type=ats_type,
                confidence=confidence,
                indicators=best_ats[1]['indicators']
            )

        return AtsDetectionResult(ats_type=None, confidence=0.0)

    def _extract_title_and_company(self, soup, ats_type: Optional[str]) -> dict:
        """Extract job title and company name from page."""
        title = None
        company_name = None

        # Try common title selectors
        title_selectors = [
            'h1',
            '[data-test-id="job-title"]',
            '.posting__title',
            '.job-title',
            '[data-qa="job-title"]',
        ]

        for selector in title_selectors:
            try:
                elem = soup.select_one(selector)
                if elem and elem.get_text(strip=True):
                    title = elem.get_text(strip=True)[:255]
                    break
            except Exception:
                pass

        # Try common company selectors
        company_selectors = [
            '[data-test-id="company-name"]',
            '.company-name',
            '[data-company]',
            '.organization-name',
            'meta[property="og:site_name"]',
        ]

        for selector in company_selectors:
            try:
                if selector.startswith('meta'):
                    elem = soup.select_one(selector)
                    if elem and elem.get('content'):
                        company_name = elem.get('content')[:255]
                        break
                else:
                    elem = soup.select_one(selector)
                    if elem and elem.get_text(strip=True):
                        company_name = elem.get_text(strip=True)[:255]
                        break
            except Exception:
                pass

        return {'title': title, 'company_name': company_name}

    def _extract_location(self, soup, ats_type: Optional[str]) -> Optional[str]:
        """Extract job location from page."""
        location_selectors = [
            '[data-test-id="job-location"]',
            '.location',
            '[data-qa="job-location"]',
            '.posting__location',
            '[itemprop="jobLocation"]',
        ]

        for selector in location_selectors:
            try:
                elem = soup.select_one(selector)
                if elem and elem.get_text(strip=True):
                    return elem.get_text(strip=True)[:255]
            except Exception:
                pass

        return None

    def _extract_description(self, soup, ats_type: Optional[str]) -> Optional[str]:
        """Extract job description from page."""
        description_selectors = [
            '[data-test-id="job-description"]',
            '.description',
            '.posting__content',
            '.job-description',
            '[itemprop="description"]',
            '.show-more-less-html',
        ]

        for selector in description_selectors:
            try:
                elem = soup.select_one(selector)
                if elem:
                    text = elem.get_text(strip=True)
                    if text and len(text) > 50:
                        return text[:5000]  # Cap at 5000 chars
            except Exception:
                pass

        return None

    def _extract_apply_url(self, soup, ats_type: Optional[str]) -> Optional[str]:
        """Extract application URL from page."""
        apply_selectors = [
            'a[data-test-id="apply-button"]',
            'a.apply-button',
            '.application-url',
            'a[href*="/apply"]',
        ]

        for selector in apply_selectors:
            try:
                elem = soup.select_one(selector)
                if elem and elem.get('href'):
                    return elem['href']
            except Exception:
                pass

        return None

    def _detect_closed_job(self, soup, html_text: str) -> bool:
        """Detect if job posting is marked as closed."""
        html_lower = html_text.lower()

        for pattern in self.CLOSED_JOB_INDICATORS:
            if re.search(pattern, html_lower):
                return True

        # Check common closed indicators in DOM
        closed_selectors = [
            '[data-closed="true"]',
            '.job-closed',
            '.posting-closed',
            '.app-status--closed',
        ]

        for selector in closed_selectors:
            try:
                if soup.select(selector):
                    return True
            except Exception:
                pass

        return False

    def _extract_fallback(self, url: str, result: dict) -> dict:
        """Fallback extraction using only URL pattern matching."""
        # Extract company name from URL patterns
        if 'greenhouse' in url.lower():
            result['ats_type'] = 'greenhouse'
            result['ats_detection_confidence'] = 0.95
            match = re.search(r'boards\.greenhouse\.io/([^/]+)', url)
            if match:
                result['company_name'] = match.group(1)

        elif 'lever.co' in url.lower():
            result['ats_type'] = 'lever'
            result['ats_detection_confidence'] = 0.95

        elif 'workday' in url.lower():
            result['ats_type'] = 'workday'
            result['ats_detection_confidence'] = 0.90

        elif 'ashby' in url.lower():
            result['ats_type'] = 'ashby'
            result['ats_detection_confidence'] = 0.90

        elif 'linkedin.com/jobs' in url.lower():
            result['ats_type'] = 'linkedin'
            result['ats_detection_confidence'] = 0.95

        result['extraction_errors'].append("Full page parsing unavailable; using URL pattern detection only")
        return result
