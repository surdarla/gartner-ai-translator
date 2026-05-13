const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const getApiUrl = (path: string) => {
  const base = API_BASE_URL.replace(/\/$/, '');
  const p = path.replace(/^\//, '');
  return `${base}/${p}`;
};

export const getWsUrl = (path: string) => {
  const base = API_BASE_URL.replace(/\/$/, '').replace(/^http/, 'ws');
  const p = path.replace(/^\//, '');
  return `${base}/${p}`;
};

export default API_BASE_URL;
