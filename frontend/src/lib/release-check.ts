import { postStream } from '$lib/stream';

export function runReleaseCheck(
  deploymentPlanKey: string,
  onText: (text: string) => void
): Promise<void> {
  return postStream('/api/release-check', { deployment_plan_key: deploymentPlanKey }, onText);
}
