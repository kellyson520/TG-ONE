import { useState, useEffect, useRef } from 'react';
import { useAppStore } from '@/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  FileText,
  Search,
  Pause,
  Play,
  ArrowDown,
  Trash2,
  Database,
  Terminal,
  AlertCircle,
  Info,
  AlertTriangle,
} from 'lucide-react';
import type { LogEntry, LogFile } from '@/types';

// Mock log files
const mockLogFiles: LogFile[] = [
  { name: 'app.log', size: 1024 * 1024 * 2.5 },
  { name: 'error.log', size: 1024 * 512 },
  { name: 'access.log', size: 1024 * 1024 * 5.2 },
  { name: 'forward.log', size: 1024 * 1024 * 1.8 },
];

// Mock log entries
const generateMockLogs = (count: number): string[] => {
  const levels = ['INFO', 'WARNING', 'ERROR', 'DEBUG'];
  const modules = ['forwarder', 'dedup', 'api', 'websocket', 'task'];
  const messages = [
    'Message forwarded successfully',
    'Duplicate message detected and filtered',
    'Connection established',
    'Task completed',
    'Processing batch',
    'Retry attempt',
    'Cache hit',
    'Rule matched',
  ];

  return Array.from({ length: count }, (_, i) => {
    const date = new Date();
    date.setSeconds(date.getSeconds() - i * 30);
    const level = levels[Math.floor(Math.random() * levels.length)];
    const module = modules[Math.floor(Math.random() * modules.length)];
    const message = messages[Math.floor(Math.random() * messages.length)];
    return `${date.toISOString().replace('T', ' ').slice(0, 19)} [${level}] [${module}] ${message}`;
  });
};

// Mock DB logs
const mockDbLogs: LogEntry[] = [
  { id: 1, timestamp: '2024-01-15T10:30:00Z', level: 'ERROR', module: 'forwarder', message: 'Failed to forward message: Connection timeout' },
  { id: 2, timestamp: '2024-01-15T10:25:00Z', level: 'WARNING', module: 'dedup', message: 'High cache memory usage detected' },
  { id: 3, timestamp: '2024-01-15T10:20:00Z', level: 'INFO', module: 'api', message: 'User login successful: admin' },
  { id: 4, timestamp: '2024-01-15T10:15:00Z', level: 'ERROR', module: 'task', message: 'Task execution failed: Rule not found' },
  { id: 5, timestamp: '2024-01-15T10:10:00Z', level: 'INFO', module: 'websocket', message: 'Client connected' },
];

export function Logs() {
  const { addNotification } = useAppStore();
  const [currentFile, setCurrentFile] = useState('app.log');
  const [logs, setLogs] = useState<string[]>(generateMockLogs(50));
  const [filteredLogs, setFilteredLogs] = useState<string[]>(logs);
  const [logLevel, setLogLevel] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [isPaused, setIsPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const logViewerRef = useRef<HTMLDivElement>(null);

  // Simulate real-time log updates
  useEffect(() => {
    if (isPaused) return;
    const interval = setInterval(() => {
      const newLog = generateMockLogs(1)[0];
      setLogs((prev) => [newLog, ...prev].slice(0, 500));
    }, 3000);
    return () => clearInterval(interval);
  }, [isPaused]);

  // Filter logs
  useEffect(() => {
    let filtered = logs;
    if (logLevel) {
      filtered = filtered.filter((log) => log.includes(`[${logLevel}]`));
    }
    if (searchQuery) {
      filtered = filtered.filter((log) =>
        log.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    setFilteredLogs(filtered);
  }, [logs, logLevel, searchQuery]);

  // Auto scroll
  useEffect(() => {
    if (autoScroll && logViewerRef.current) {
      logViewerRef.current.scrollTop = logViewerRef.current.scrollHeight;
    }
  }, [filteredLogs, autoScroll]);

  const getLogLevel = (log: string): string => {
    const match = log.match(/\[(\w+)\]/);
    return match ? match[1] : 'INFO';
  };

  const getLogColor = (level: string): string => {
    switch (level) {
      case 'ERROR':
        return 'text-red-500 border-red-500';
      case 'WARNING':
        return 'text-amber-500 border-amber-500';
      case 'DEBUG':
        return 'text-sky-500 border-sky-500';
      default:
        return 'text-emerald-500 border-emerald-500';
    }
  };

  const clearLogs = () => {
    setLogs([]);
    addNotification({ message: '日志已清空', type: 'info' });
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Log Files */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <FileText className="w-4 h-4 text-primary" />
              日志文件
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {mockLogFiles.map((file) => (
                <button
                  key={file.name}
                  onClick={() => setCurrentFile(file.name)}
                  className={`w-full flex items-center justify-between p-3 rounded-lg text-left transition-all ${
                    currentFile === file.name
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted hover:bg-muted/80'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4" />
                    <span className="text-sm">{file.name}</span>
                  </div>
                  <span className="text-xs opacity-70">
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Log Viewer */}
        <Card className="lg:col-span-3">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Terminal className="w-4 h-4 text-primary" />
              {currentFile}
            </CardTitle>
            <div className="flex items-center gap-2">
              <Select value={logLevel} onValueChange={setLogLevel}>
                <SelectTrigger className="w-32 h-8">
                  <SelectValue placeholder="所有级别" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">所有级别</SelectItem>
                  <SelectItem value="ERROR">错误</SelectItem>
                  <SelectItem value="WARNING">警告</SelectItem>
                  <SelectItem value="INFO">信息</SelectItem>
                  <SelectItem value="DEBUG">调试</SelectItem>
                </SelectContent>
              </Select>

              <div className="relative">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground" />
                <Input
                  placeholder="搜索..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-40 h-8 pl-7 text-sm"
                />
              </div>

              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                onClick={() => setIsPaused(!isPaused)}
              >
                {isPaused ? (
                  <Play className="w-4 h-4 text-emerald-500" />
                ) : (
                  <Pause className="w-4 h-4 text-amber-500" />
                )}
              </Button>

              <Button
                variant="outline"
                size="icon"
                className={`h-8 w-8 ${autoScroll ? 'bg-primary/10' : ''}`}
                onClick={() => setAutoScroll(!autoScroll)}
              >
                <ArrowDown className="w-4 h-4" />
              </Button>

              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8 text-red-500"
                onClick={clearLogs}
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div
              ref={logViewerRef}
              className="log-viewer font-mono text-sm"
              onScroll={() => {
                if (logViewerRef.current) {
                  const { scrollTop, scrollHeight, clientHeight } = logViewerRef.current;
                  setAutoScroll(scrollHeight - scrollTop - clientHeight < 50);
                }
              }}
            >
              {filteredLogs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <FileText className="w-12 h-12 mx-auto mb-2 opacity-25" />
                  暂无日志
                </div>
              ) : (
                filteredLogs.map((log, index) => {
                  const level = getLogLevel(log);
                  return (
                    <div
                      key={index}
                      className={`log-line border-l-2 ${getLogColor(level)}`}
                    >
                      <span className="opacity-70">{log.slice(0, 19)}</span>
                      <span className={`ml-2 font-medium ${getLogColor(level).split(' ')[0]}`}>
                        [{level}]
                      </span>
                      <span className="ml-2">{log.slice(log.indexOf(']') + 2)}</span>
                    </div>
                  );
                })
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Database Logs */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Database className="w-4 h-4 text-primary" />
            数据库记录
          </CardTitle>
          <Button variant="outline" size="sm">
            加载记录
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-16">ID</TableHead>
                <TableHead className="w-40">时间</TableHead>
                <TableHead className="w-24">级别</TableHead>
                <TableHead className="w-32">模块</TableHead>
                <TableHead>消息</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockDbLogs.map((log) => (
                <TableRow key={log.id}>
                  <TableCell className="text-muted-foreground">#{log.id}</TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {new Date(log.timestamp).toLocaleString('zh-CN')}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        log.level === 'ERROR'
                          ? 'destructive'
                          : log.level === 'WARNING'
                          ? 'secondary'
                          : 'default'
                      }
                      className={
                        log.level === 'INFO'
                          ? 'bg-emerald-500/10 text-emerald-500'
                          : log.level === 'WARNING'
                          ? 'bg-amber-500/10 text-amber-500'
                          : ''
                      }
                    >
                      {log.level === 'ERROR' && <AlertCircle className="w-3 h-3 mr-1" />}
                      {log.level === 'WARNING' && <AlertTriangle className="w-3 h-3 mr-1" />}
                      {log.level === 'INFO' && <Info className="w-3 h-3 mr-1" />}
                      {log.level}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <code className="text-xs bg-muted px-2 py-1 rounded">{log.module}</code>
                  </TableCell>
                  <TableCell className="max-w-md truncate">{log.message}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
