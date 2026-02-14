import { useState } from 'react';
import { useAppStore } from '@/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Cpu,
  RefreshCw,
  Database,
  CheckCircle,
  Info,
  Play,
  Search,
} from 'lucide-react';
import type { ArchiveStatus } from '@/types';

// Mock archive data
const mockArchiveStatus: ArchiveStatus = {
  sqlite_counts: {
    rule_logs: 15234,
    rule_statistics: 8921,
    chat_statistics: 4567,
    error_logs: 1234,
    media_signatures: 34567,
    task_queue: 890,
  },
  archive_config: {
    rule_logs: 30,
    rule_statistics: 90,
    chat_statistics: 90,
    error_logs: 180,
    media_signatures: 7,
    task_queue: 7,
  },
  is_running: false,
};

const tableNames: Record<string, string> = {
  rule_logs: '转发日志',
  rule_statistics: '规则统计',
  chat_statistics: '聊天统计',
  error_logs: '系统错误',
  media_signatures: '媒体指纹',
  task_queue: '任务队列',
};

export function ArchivePage() {
  const { addNotification } = useAppStore();
  const [archiveStatus, setArchiveStatus] = useState<ArchiveStatus>(mockArchiveStatus);
  const [isLoading, setIsLoading] = useState(false);

  const refreshStatus = () => {
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      addNotification({ message: '状态已刷新', type: 'info' });
    }, 500);
  };

  const triggerArchive = () => {
    if (!confirm('启动归档将进行大规模 IO 操作，确定现在执行吗？')) return;
    
    setArchiveStatus((prev) => ({ ...prev, is_running: true }));
    
    // Simulate archiving process
    setTimeout(() => {
      setArchiveStatus((prev) => ({ ...prev, is_running: false }));
      addNotification({ message: '归档任务已完成', type: 'success' });
    }, 5000);
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Archive Status */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Database className="w-4 h-4 text-primary" />
              热数据存量 (SQLite)
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={refreshStatus}
                disabled={isLoading}
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                刷新
              </Button>
              <Button
                size="sm"
                className="gradient-primary"
                onClick={triggerArchive}
                disabled={archiveStatus.is_running}
              >
                {archiveStatus.is_running ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                ) : (
                  <Play className="w-4 h-4 mr-2" />
                )}
                {archiveStatus.is_running ? '归档中...' : '立即归档'}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>数据对象</TableHead>
                  <TableHead>记录数</TableHead>
                  <TableHead>保留周期</TableHead>
                  <TableHead className="w-16"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(archiveStatus.sqlite_counts).map(([key, count]) => (
                  <TableRow key={key}>
                    <TableCell>
                      <div className="font-medium">{tableNames[key] || key}</div>
                      <div className="text-xs text-muted-foreground font-mono">{key}</div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="bg-primary/10 text-primary">
                        {count.toLocaleString()}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="bg-sky-500/10 text-sky-500">
                        {archiveStatus.archive_config[key]} 天
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="icon" className="h-8 w-8" disabled>
                        <Search className="w-4 h-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Engine Status */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Cpu className="w-4 h-4 text-info" />
              引擎状态
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 rounded-lg bg-muted">
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
                当前状态
              </div>
              <div className="flex items-center gap-3">
                <div
                  className={`w-3 h-3 rounded-full ${
                    archiveStatus.is_running
                      ? 'bg-emerald-500 animate-pulse'
                      : 'bg-sky-500'
                  }`}
                />
                <span className="font-medium">
                  {archiveStatus.is_running ? '正在执行归档...' : '节点就绪 (空闲中)'}
                </span>
              </div>
            </div>

            <Alert className="bg-sky-500/10 border-sky-500/20">
              <Info className="w-4 h-4 text-sky-500" />
              <AlertDescription className="text-sm">
                归档逻辑按天级别滚动，将 SQLite 记录持久化至{' '}
                <code className="bg-muted px-1 rounded">/archives</code> 目录。
              </AlertDescription>
            </Alert>

            <div>
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-3">
                配置策略预览
              </div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(archiveStatus.archive_config).map(([key, days]) => (
                  <Badge key={key} variant="secondary" className="text-xs">
                    {key}: {days}d
                  </Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Parquet Storage Info */}
      <Card>
        <CardContent className="p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-8 h-8 text-emerald-500" />
          </div>
          <h3 className="text-lg font-semibold mb-2">Parquet 冷存储就绪</h3>
          <p className="text-muted-foreground max-w-lg mx-auto">
            归档数据已分区存储，您可以使用分析工具通过 SQL (DuckDB) 直接读取{' '}
            <code className="bg-muted px-1 rounded">ARCHIVE_ROOT</code> 下的文件。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
