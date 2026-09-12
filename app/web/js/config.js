// config.js — 环境配置
// 云端部署时在 index.html 注入 window.__API_BASE__；Supabase 为只读直连（publishable key 设计上公开）
export const API_BASE = window.__API_BASE__ || 'http://127.0.0.1:8791';
export const SUPABASE_URL = 'https://mqsqcpkcmcgwbzcsmrlm.supabase.co';
export const SUPABASE_ANON_KEY = 'sb_publishable_3pQRAq-R_5Ux9DS8bWHt3A_Kr0v4Dd0';
