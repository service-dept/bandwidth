/**
 * Cloudflare Worker to trigger Pages rebuild on cron schedule.
 *
 * This worker runs every 10 minutes and triggers a new build
 * of the bandwidth site via Cloudflare Pages deploy hook.
 *
 * Setup:
 * 1. Create a deploy hook in Cloudflare Pages dashboard
 * 2. Add the hook URL as a secret: DEPLOY_HOOK_URL
 * 3. Deploy this worker with: wrangler deploy
 */

export default {
  async scheduled(event, env, ctx) {
    // Trigger Pages rebuild via deploy hook
    const response = await fetch(env.DEPLOY_HOOK_URL, {
      method: 'POST',
    });

    if (!response.ok) {
      console.error(`Deploy hook failed: ${response.status}`);
      throw new Error(`Deploy hook failed: ${response.status}`);
    }

    console.log('Deploy triggered successfully');
  },
};
