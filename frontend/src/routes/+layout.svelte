<script lang="ts">
  import '../app.css';

  let dark = false;

  function toggleTheme() {
    dark = !dark;
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  }
</script>

<div class="page">
  <header class="topbar card">
    <div>
      <h1>CareerSidekick</h1>
      <p class="muted">Your trusty job-hunting buddy.</p>
    </div>
    <div class="actions">
      <a class="btn" href="/dashboard">Dashboard</a>
      <a class="btn" href="/approval">Approval Panel</a>
      <a class="btn" href="/live-run">Live Run Viewer</a>
      <button class="btn" on:click={toggleTheme}>{dark ? 'Light' : 'Dark'} mode</button>
    </div>
  </header>

  <main>
    <slot />
  </main>
</div>

<style>
  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 16px;
    margin-bottom: 20px;
  }

  .topbar h1 {
    margin: 0;
    font-size: 1.4rem;
  }

  .topbar p {
    margin: 4px 0 0;
  }

  .actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  main {
    min-height: 70vh;
  }
</style>
