import { request } from './api.js';

export async function calculateFootprint(profileId, periodStart, periodEnd) {
  return request(`/api/profiles/${profileId}/footprint/calculate`, {
    method: 'POST',
    body: JSON.stringify({ period_start: periodStart, period_end: periodEnd }),
  });
}

export async function getFootprintHistory(profileId) {
  return request(`/api/profiles/${profileId}/footprint/history`);
}

export async function getLatestFootprint(profileId) {
  return request(`/api/profiles/${profileId}/footprint/latest`);
}
