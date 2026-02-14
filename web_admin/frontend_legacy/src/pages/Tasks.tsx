import { useState, useEffect } from 'react';
import { useAppStore } from '@/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
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
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';
import {
  Zap,
  RefreshCw,
  Info,
  Clock,
  AlertCircle,
  CheckCircle,
  Loader2,
} from 'lucide-react';
import type { Task } from '@/types';

// Mock tasks data
const mockTasks: Task[] = [
  {
    id: 1,
    type: 'forward',
    status: 'running',
    unique_key: 'msg_12345',
    priority: 5,
    retry_count: 0,
    progress: 65,
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-15T10:30:30Z',
  },
  {
    id: 2,
    type: 'download',
    status: 'pending',
    unique_key: 'media_67890',
    priority: 3,
    retry_count: 0,
    created_at: '2024-01-15T10:25:00Z',
    updated_at: '2024-01-15T10:25:00Z',
  },
  {
    id: 3,
    type: 'archive',
    status: 'completed',
    unique_key: 'archive_001',
    priority: 1,
    retry_count: 0,
    progress: 100,
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:15:00Z',
  },
  {
    id: 4,
    type: 'forward',
    status: 'failed',
    unique_key: 'msg_12346',
    priority: 5,
    retry_count: 2,
    created_at: '2024-01-15T10:20:00Z',
    updated_at: '2024-01-15T10:28:00Z',
    error_log: 'Connection timeout after 30s',
  },
  {
    id: 5,
    type: 'dedup',
    status: 'running',
    unique_key: 'dedup_batch_1',
    priority: 2,
    retry_count: 0,
    progress: 42,
    created_at: '2024-01-15T10:28:00Z',
    updated_at: '2024-01-15T10:29:00Z',
  },
];

export function Tasks() {
  const { addNotification } = useAppStore();
  const [tasks, setTasks] = useState<Task[]>(mockTasks);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);

  const filteredTasks = tasks.filter((task) =>
    statusFilter ? task.status === statusFilter : true
  );

  const itemsPerPage = 10;
  const totalPages = Math.ceil(filteredTasks.length / itemsPerPage);
  const paginatedTasks = filteredTasks.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  // Simulate real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      setTasks((prev) =>
        prev.map((task) => {
          if (task.status === 'running' && task.progress !== undefined) {
            return {
              ...task,
              progress: Math.min(100, task.progress + Math.random() * 5),
            };
          }
          return task;
        })
      );
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const refreshTasks = () => {
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      addNotification({ message: '任务列表已刷新', type: 'info' });
    }, 500);
  };

  const getStatusBadge = (status: string) => {
    const configs: Record<string, { label: string; className: string; icon: React.ElementType }> = {
      pending: {
        label: '待处理',
        className: 'bg-amber-500/10 text-amber-500',
        icon: Clock,
      },
      running: {
        label: '运行中',
        className: 'bg-primary/10 text-primary',
        icon: Loader2,
      },
      completed: {
        label: '已完成',
        className: 'bg-emerald-500/10 text-emerald-500',
        icon: CheckCircle,
      },
      failed: {
        label: '失败',
        className: 'bg-red-500/10 text-red-500',
        icon: AlertCircle,
      },
    };
    const config = configs[status] || configs.pending;
    const Icon = config.icon;
    return (
      <Badge variant="secondary" className={config.className}>
        <Icon className={`w-3 h-3 mr-1 ${status === 'running' ? 'animate-spin' : ''}`} />
        {config.label}
      </Badge>
    );
  };

  const viewDetails = (task: Task) => {
    if (task.error_log) {
      addNotification({
        message: `任务 #${task.id} 错误: ${task.error_log}`,
        type: 'error',
      });
    } else {
      addNotification({
        message: `任务 #${task.id} 运行正常`,
        type: 'info',
      });
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary" />
            任务队列
          </CardTitle>
          <div className="flex items-center gap-2">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">全部状态</SelectItem>
                <SelectItem value="pending">待处理</SelectItem>
                <SelectItem value="running">运行中</SelectItem>
                <SelectItem value="completed">已完成</SelectItem>
                <SelectItem value="failed">失败</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="icon" onClick={refreshTasks} disabled={isLoading}>
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-16">ID</TableHead>
                <TableHead className="w-28">类型</TableHead>
                <TableHead className="w-28">状态</TableHead>
                <TableHead>目标标识</TableHead>
                <TableHead className="w-20">权重</TableHead>
                <TableHead className="w-20">重试</TableHead>
                <TableHead className="w-48">时间追踪</TableHead>
                <TableHead className="w-16 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedTasks.map((task) => (
                <TableRow key={task.id}>
                  <TableCell className="text-muted-foreground">#{task.id}</TableCell>
                  <TableCell>
                    <code className="text-xs bg-muted px-2 py-1 rounded">{task.type}</code>
                  </TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      {getStatusBadge(task.status)}
                      {task.status === 'running' && task.progress !== undefined && (
                        <Progress value={task.progress} className="h-1 w-24" />
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="text-sm truncate max-w-[200px]" title={task.unique_key}>
                      <span className="text-muted-foreground">路由键:</span> {task.unique_key}
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className="text-muted-foreground">{task.priority}</span>
                  </TableCell>
                  <TableCell>
                    {task.retry_count > 0 ? (
                      <Badge variant="secondary" className="bg-amber-500/10 text-amber-500">
                        {task.retry_count}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">0</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="text-xs text-muted-foreground">
                      <div>入队: {new Date(task.created_at).toLocaleString('zh-CN')}</div>
                      <div>更新: {new Date(task.updated_at).toLocaleString('zh-CN')}</div>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => viewDetails(task)}
                    >
                      <Info className="w-4 h-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {paginatedTasks.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              <Zap className="w-12 h-12 mx-auto mb-2 opacity-25" />
              当前队列无任务
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <div className="text-sm text-muted-foreground">
                显示 {filteredTasks.length} 个任务中第 {currentPage} 页
              </div>
              <Pagination>
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      className={currentPage === 1 ? 'pointer-events-none opacity-50' : ''}
                    />
                  </PaginationItem>
                  <PaginationItem>
                    <PaginationLink>{currentPage}</PaginationLink>
                  </PaginationItem>
                  <PaginationItem>
                    <PaginationNext
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      className={
                        currentPage === totalPages ? 'pointer-events-none opacity-50' : ''
                      }
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
