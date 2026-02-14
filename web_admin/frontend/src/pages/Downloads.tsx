import { useState, useEffect } from 'react';
import { useAppStore } from '@/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  CloudDownload,
  CheckCircle,
  Download,
  Trash2,
  Pause,
  Play,
  Activity,
} from 'lucide-react';
import type { DownloadTask } from '@/types';

// Mock download tasks
const mockDownloads: DownloadTask[] = [
  {
    id: '1',
    name: 'image_2024_01_15_001.jpg',
    size: '2.5 MB',
    progress: 75,
    speed: '1.2 MB/s',
    status: 'downloading',
  },
  {
    id: '2',
    name: 'video_2024_01_15_002.mp4',
    size: '156.8 MB',
    progress: 45,
    speed: '5.6 MB/s',
    status: 'downloading',
  },
  {
    id: '3',
    name: 'document_2024_01_15_003.pdf',
    size: '1.2 MB',
    progress: 100,
    speed: '-',
    status: 'completed',
  },
  {
    id: '4',
    name: 'audio_2024_01_15_004.mp3',
    size: '8.5 MB',
    progress: 0,
    speed: '-',
    status: 'paused',
  },
  {
    id: '5',
    name: 'archive_2024_01_15_005.zip',
    size: '45.2 MB',
    progress: 30,
    speed: '0 KB/s',
    status: 'failed',
  },
];

export function Downloads() {
  const { addNotification } = useAppStore();
  const [downloads, setDownloads] = useState<DownloadTask[]>(mockDownloads);
  const [stats] = useState({
    activeTasks: 2,
    completedToday: 156,
    networkTraffic: 12.5,
  });

  // Simulate progress updates
  useEffect(() => {
    const interval = setInterval(() => {
      setDownloads((prev) =>
        prev.map((task) => {
          if (task.status === 'downloading' && task.progress < 100) {
            return {
              ...task,
              progress: Math.min(100, task.progress + Math.random() * 2),
            };
          }
          return task;
        })
      );
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const handlePauseResume = (id: string) => {
    setDownloads((prev) =>
      prev.map((task) =>
        task.id === id
          ? { ...task, status: task.status === 'downloading' ? 'paused' : 'downloading' }
          : task
      )
    );
    addNotification({ message: '任务状态已更新', type: 'info' });
  };

  const handleDelete = (id: string) => {
    setDownloads((prev) => prev.filter((task) => task.id !== id));
    addNotification({ message: '任务已删除', type: 'success' });
  };

  const clearCache = () => {
    addNotification({ message: '缓存已清理', type: 'success' });
  };

  const getStatusBadge = (status: string) => {
    const configs: Record<string, { label: string; className: string }> = {
      downloading: {
        label: '下载中',
        className: 'bg-primary/10 text-primary',
      },
      completed: {
        label: '已完成',
        className: 'bg-emerald-500/10 text-emerald-500',
      },
      paused: {
        label: '已暂停',
        className: 'bg-amber-500/10 text-amber-500',
      },
      failed: {
        label: '失败',
        className: 'bg-red-500/10 text-red-500',
      },
    };
    const config = configs[status] || configs.downloading;
    return (
      <Badge variant="secondary" className={config.className}>
        {config.label}
      </Badge>
    );
  };

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">活跃任务</p>
                <p className="text-3xl font-bold">{stats.activeTasks}</p>
                <Badge variant="secondary" className="mt-2 bg-primary/10 text-primary">
                  处理中
                </Badge>
              </div>
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <CloudDownload className="w-5 h-5 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">今日完成</p>
                <p className="text-3xl font-bold">{stats.completedToday}</p>
                <Badge variant="secondary" className="mt-2 bg-emerald-500/10 text-emerald-500">
                  今日
                </Badge>
              </div>
              <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                <CheckCircle className="w-5 h-5 text-emerald-500" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">实时带宽</p>
                <p className="text-3xl font-bold">{stats.networkTraffic.toFixed(2)}</p>
                <p className="text-xs text-muted-foreground mt-2">MB/s</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-sky-500/10 flex items-center justify-center">
                <Activity className="w-5 h-5 text-sky-500" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Download List */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Download className="w-4 h-4 text-primary" />
            任务队列
          </CardTitle>
          <Button variant="outline" size="sm" onClick={clearCache}>
            <Trash2 className="w-4 h-4 mr-2" />
            清理缓存
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>资源名称</TableHead>
                <TableHead className="w-24">大小</TableHead>
                <TableHead className="w-48">进度</TableHead>
                <TableHead className="w-24">速度</TableHead>
                <TableHead className="w-24">状态</TableHead>
                <TableHead className="w-24 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {downloads.map((task) => (
                <TableRow key={task.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <CloudDownload className="w-4 h-4 text-muted-foreground" />
                      <span className="font-medium truncate max-w-[200px]">{task.name}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{task.size}</TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-muted-foreground">进度</span>
                        <span>{task.progress.toFixed(0)}%</span>
                      </div>
                      <Progress value={task.progress} className="h-2" />
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{task.speed}</TableCell>
                  <TableCell>{getStatusBadge(task.status)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      {task.status !== 'completed' && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => handlePauseResume(task.id)}
                        >
                          {task.status === 'downloading' ? (
                            <Pause className="w-4 h-4" />
                          ) : (
                            <Play className="w-4 h-4" />
                          )}
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-red-500"
                        onClick={() => handleDelete(task.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {downloads.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              <CloudDownload className="w-12 h-12 mx-auto mb-2 opacity-25" />
              当前暂无正在进行的任务
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
