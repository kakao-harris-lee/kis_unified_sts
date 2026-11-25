import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add API key header if configured
const apiKey = process.env.NEXT_PUBLIC_API_KEY;
if (apiKey) {
  apiClient.defaults.headers.common['X-API-Key'] = apiKey;
}
