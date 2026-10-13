const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function request(path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(body?.error?.message || body?.detail?.message || 'CarbonOS service is unavailable');
  return body;
}

export async function getHealth() {
  return request('/api/health');
}

export const getSavedProfileId = () => window.localStorage.getItem('carbonos.profileId');

export async function saveOnboarding({ selections }) {
  const household = selections[1];
  const facts = [
    selections[2] && { key: 'usual_travel', value: selections[2] },
    selections[5] && { key: 'typical_diet', value: selections[5] },
    selections[6] && { key: 'shopping_habits', value: selections[6] },
    household === '3–4 people' && { key: 'household_size_range', value: household },
    household === '5 or more' && { key: 'household_size_range', value: household },
  ].filter(Boolean).map(fact => ({ ...fact, source: 'ONBOARDING', confidence: 1, confirmed: true }));
  const assets = [
    ...(Array.isArray(selections[3]) ? selections[3] : [selections[3]]).filter(value => value && value !== 'I don’t own one').map(name => ({ asset_type: 'VEHICLE', name, source: 'ONBOARDING', confidence: 1 })),
    ...(Array.isArray(selections[4]) ? selections[4] : [selections[4]]).filter(value => value && value !== 'I’ll add this later').map(name => ({ asset_type: 'APPLIANCE', name, source: 'ONBOARDING', confidence: 1 })),
  ];
  const profile = await request('/api/profiles/onboarding', {
    method: 'POST',
    body: JSON.stringify({
      profile: {
        display_name: '', country_code: 'IN',
        city: selections[0] && selections[0] !== 'Somewhere else' ? selections[0] : null,
        household_size: household === 'Just me' ? 1 : household === '2 people' ? 2 : null,
        preferences: { region: 'IN' },
      }, facts, assets,
    }),
  });
  window.localStorage.setItem('carbonos.profileId', profile.id);
  return profile;
}

export async function getPersistedProfile(profileId) {
  const [profile, facts, assets] = await Promise.all([
    request(`/api/profiles/${profileId}`),
    request(`/api/profiles/${profileId}/facts`),
    request(`/api/profiles/${profileId}/assets?include_inactive=true`),
  ]);
  return { profile, facts, assets };
}

export async function getPersistedActivities(profileId) {
  return request(`/api/profiles/${profileId}/activities`);
}

export async function updatePersistedProfile(profileId, changes) {
  return request(`/api/profiles/${profileId}`, { method: 'PATCH', body: JSON.stringify(changes) });
}

export async function updatePersistedAsset(profileId, assetId, changes) {
  return request(`/api/profiles/${profileId}/assets/${assetId}`, { method: 'PATCH', body: JSON.stringify(changes) });
}

export async function createPersistedAsset(profileId, asset) {
  return request(`/api/profiles/${profileId}/assets`, { method: 'POST', body: JSON.stringify(asset) });
}

export async function retirePersistedAsset(profileId, assetId) {
  return request(`/api/profiles/${profileId}/assets/${assetId}/retire`, { method: 'POST' });
}

export async function createPersistedActivity(profileId, activity) {
  return request(`/api/profiles/${profileId}/activities`, { method: 'POST', body: JSON.stringify(activity) });
}

export async function updatePersistedActivity(profileId, activityId, activity) {
  return request(`/api/profiles/${profileId}/activities/${activityId}`, { method: 'PATCH', body: JSON.stringify(activity) });
}

export async function deletePersistedActivity(profileId, activityId) {
  return request(`/api/profiles/${profileId}/activities/${activityId}`, { method: 'DELETE' });
}
