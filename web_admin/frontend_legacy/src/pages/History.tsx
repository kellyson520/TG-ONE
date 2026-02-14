import { useState } from 'react';
import { useAppStore } from '@/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
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
  Clock,
  Search,
  CheckCircle,
  XCircle,
  Info,
} from 'lucide-react';
import type { HistoryEntry } from '@/types';

// Mock history data
const mockHistory: HistoryEntry[] = Array.from({ length: 50 }, (_, i) => ({
  id: i + 1,
  created_at: new Date(Date.now() - i * 60000).toISOString(),
  source_chat: ['新闻源频道', '技术讨论组', '监控告警', '产品更新', '内部公告'][i % 5],
  target_chat: ['聚合推送群', '技术归档', '值班群', '用户通知', '全员群'][i % 5],
  action: ['转发', '过滤', '去重', '替换'][i % 4],
  result: Math.random() > 0.1 ? 'success' : 'failed',
  error_message: Math.random() > 0.9 ? 'Connection timeout' : undefined,
}));

export function History() {
  const { addNotification } = useAppStore();
  const [history] = useState<HistoryEntry[]>(mockHistory);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  const filteredHistory = history.filter(
    (item) =>
      item.source_chat.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.target_chat.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.action.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const itemsPerPage = 15;
  const totalPages = Math.ceil(filteredHistory.length / itemsPerPage);
  const paginatedHistory = filteredHistory.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const viewDetail = (entry: HistoryEntry) => {
    addNotification({
      message: `查看记录 #${entry.id} 详情`,
      type: 'info',
    });
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Clock className="w-4 h-4 text-primary" />
            执行记录
          </CardTitle>
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="按内容或来源搜索..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-32">时间戳</TableHead>
                <TableHead>来源实体</TableHead>
                <TableHead>目标实体</TableHead>
                <TableHead className="w-24">动作</TableHead>
                <TableHead className="w-24">状态</TableHead>
                <TableHead>详情</TableHead>
                <TableHead className="w-16 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedHistory.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="text-muted-foreground text-sm">
                    {new Date(entry.created_at).toLocaleString('zh-CN')}
                  </TableCell>
                  <TableCell>
                    <div className="font-medium truncate max-w-[120px]" title={entry.source_chat}>
                      {entry.source_chat}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="font-medium truncate max-w-[120px]" title={entry.target_chat}>
                      {entry.target_chat}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="bg-primary/10 text-primary">
                      {entry.action}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={entry.result === 'success' ? 'default' : 'destructive'}
                      className={
                        entry.result === 'success'
                          ? 'bg-emerald-500/10 text-emerald-500'
                          : ''
                      }
                    >
                      {entry.result === 'success' ? (
                        <CheckCircle className="w-3 h-3 mr-1" />
                      ) : (
                        <XCircle className="w-3 h-3 mr-1" />
                      )}
                      {entry.result === 'success' ? '成功' : '失败'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="text-sm text-muted-foreground truncate max-w-[200px]">
                      {entry.error_message || '-'}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => viewDetail(entry)}
                    >
                      <Info className="w-4 h-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {paginatedHistory.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              <Clock className="w-12 h-12 mx-auto mb-2 opacity-25" />
              暂无历史记录
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
              <div className="text-sm text-muted-foreground">
                第 {currentPage} / {totalPages} 页
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
