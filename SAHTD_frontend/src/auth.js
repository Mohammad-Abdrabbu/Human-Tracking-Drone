// src/auth.js

const TOKEN_KEY = 'sahtd_access_token';
const ROLE_KEY = 'sahtd_role';

export function saveAuth(token, role) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ROLE_KEY, role);
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRole() {
  return localStorage.getItem(ROLE_KEY);
}

export function isAuthenticated() {
  return !!getToken();
}
