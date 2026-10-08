<script lang="ts">
  import { resolve } from '$app/paths';
  import { tools } from '$lib/tools';
</script>

<svelte:head>
  <title>Release Management Tools</title>
  <meta
    name="description"
    content="Release Management Tools runs the team's Jira release scripts from one place, with a log for every run."
  />
</svelte:head>

<main>
  <section class="splash" aria-labelledby="page-title">
    <h1 id="page-title">Release Management Tools</h1>
    <p class="lead">
      One place to run the Jira release scripts, with a log for every run. Each tool wraps a script
      the release team used to run by hand, so the steps are the same every time and nothing is
      hidden.
    </p>

    <h2>Tools</h2>
    <ul class="tool-list">
      {#each tools as tool (tool.route)}
        <li>
          <a class="tool-card" href={resolve(tool.route)}>
            <span class="tool-tag" class:tool-tag-writes={tool.access === 'Changes Jira'}>
              {tool.access}
            </span>
            <span class="tool-title">{tool.title}</span>
            <span class="tool-summary">{tool.summary}</span>
            <span class="tool-open">Open Tool</span>
          </a>
        </li>
      {/each}
    </ul>

    <h2>How It Works</h2>
    <ol class="steps">
      <li>
        <strong>Choose a tool</strong> from the list above or the Select a Tool menu at the top.
      </li>
      <li>
        <strong>Check the note</strong> above the button. It says exactly what the run will do before
        you start it.
      </li>
      <li>
        <strong>Run it and read the log.</strong> The script log shows every step, and warnings are highlighted.
      </li>
    </ol>

    <h2>Safe By Default</h2>
    <p class="notice">
      Tools that change Jira start with <strong>Dry Run</strong> turned on, which only lists what
      would happen. A run that will really change Jira turns the button red and labels it
      <strong>(Live)</strong>. Nothing runs until you click the button, and the Jira token never
      leaves the server.
    </p>
  </section>
</main>
