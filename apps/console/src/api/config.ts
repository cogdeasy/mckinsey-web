export interface ApiConfig {
  baseUrl: string;
  token: string | undefined;
}

export function readApiConfig(): ApiConfig {
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
  const token = import.meta.env.VITE_API_TOKEN;
  return { baseUrl: baseUrl.replace(/\/$/, ''), token: token ? token : undefined };
}
