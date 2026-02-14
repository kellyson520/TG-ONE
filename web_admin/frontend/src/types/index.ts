// User types
export interface User {
  id: number;
  username: string;
  email?: string;
  is_admin: boolean;
  is_active: boolean;
  login_count: number;
  last_login?: string;
  is_2fa_enabled?: boolean;
}

// Rule types
export interface Rule {
  id: number;
  source_chat_id: string;
  target_chat_id: string;
  source_chat?: {
    title: string;
  };
  target_chat?: {
    title: string;
  };
  enabled: boolean;
  enable_dedup: boolean;
  keywords?: Keyword[];
  keywords_count?: number;
  replace_rules_count?: number;
  forwards?: number;
  errors?: number;
}

export interface Keyword {
  id: number;
  keyword: string;
}

// Stats types
export interface StatsOverview {
  overview: {
    active_rules: number;
    total_rules: number;
  };
  forward_stats: {
    total_forwards: number;
    error_count: number;
  };
  dedup_stats: {
    cached_signatures: number;
    saved_size_mb: number;
  };
}

export interface SystemResources {
  cpu_percent: number;
  memory_percent: number;
  db_size_mb: number;
}

// Log types
export interface LogEntry {
  id: number;
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  module: string;
  message: string;
}

export interface LogFile {
  name: string;
  size: number;
}

// Task types
export interface Task {
  id: number;
  type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  unique_key?: string;
  priority: number;
  retry_count: number;
  progress?: number;
  created_at: string;
  updated_at: string;
  error_log?: string;
}

// History types
export interface HistoryEntry {
  id: number;
  created_at: string;
  source_chat: string;
  target_chat: string;
  action: string;
  result: string;
  error_message?: string;
}

// Audit log types
export interface AuditLog {
  id: number;
  timestamp: string;
  username: string;
  action: string;
  ip_address?: string;
  status: 'success' | 'failed';
  details?: string;
}

// ACL types
export interface ACLRule {
  ip_address: string;
  type: 'ALLOW' | 'BLOCK';
  reason?: string;
}

// Archive types
export interface ArchiveStatus {
  sqlite_counts: Record<string, number>;
  archive_config: Record<string, number>;
  is_running: boolean;
}

// Settings types
export interface Setting {
  key: string;
  label: string;
  type: 'string' | 'integer' | 'boolean';
  value?: string | number | boolean;
  options?: string[];
  group: string;
  sensitive?: boolean;
  requires_restart?: boolean;
  min?: number;
  max?: number;
}

// Download types
export interface DownloadTask {
  id: string;
  name: string;
  size: string;
  progress: number;
  speed: string;
  status: 'downloading' | 'completed' | 'failed' | 'paused';
}

// Visualization types
export interface GraphNode {
  id: string;
  type: 'chat' | 'rule';
  label: string;
  data: Record<string, any>;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// Notification types
export interface Notification {
  id: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  duration?: number;
}

// Theme type
export type Theme = 'light' | 'dark';
