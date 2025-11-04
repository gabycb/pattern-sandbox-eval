import type { AgentMessage, Plan } from '../lib/api';

export interface ChatRunResult {
  plan: Plan;
  messages: AgentMessage[];
}
