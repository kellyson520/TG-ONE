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
  Shield,
  Search,
  CheckCircle,
  XCircle,
  Filter,
} from 'lucide-react';
import type { AuditLog } from '@/types';

// Mock audit logs
const mockAuditLogs: AuditLog[] = Array.from({ length: 45 }, (_, i) => ({
  id: i + 1,
  timestamp: new Date(Date.now() - i * 3600000).toISOString(),
  username: ['admin', 'operator1', 'operator2', 'system'][i % 4],
  action: ['LOGIN', 'LOGOUT', 'RULE_CREATE', 'RULE_UPDATE', 'RULE_DELETE', 'SETTINGS_CHANGE'][i % 6],
  ip_address: `192.168.1.${(i % 255) + 1}`,
  status: Math.random() > 0.1 ? 'success' : 'failed',
  details: [
    '用户登录成功',
    '创建转发规则 #123',
    '更新系统设置',
    '删除规则 #456',
    '导出规则配置',
  ][i % 5],
}));

export function AuditLogs() {
  const { addNotification } = useAppStore();
  const [logs] = useState<AuditLog[]>(mockAuditLogs);
  const [actionFilter, setActionFilter] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  const filteredLogs = logs.filter((log) =>
    actionFilter ? log.action.toLowerCase().includes(actionFilter.toLowerCase()) : true
  );

  const itemsPerPage = 15;
  const totalPages = Math.ceil(filteredLogs.length / itemsPerPage);
  const paginatedLogs = filteredLogs.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const queryLogs = () => {
    addNotification({ message: '审计日志已刷新', type: 'info' });
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Shield className="w-4 h-4 text-primary" />
            操作流水
          </CardTitle>
          <div className="flex items-center gap-2">
            <div className="relative w-48">
              <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="筛选操作 (如: LOGIN)"
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
                className="pl-10"
                onKeyPress={(e) => e.key === 'Enter' && queryLogs()}
              />
            </div>
            <Button className="gradient-primary" onClick={queryLogs}>
              <Search className="w-4 h-4 mr-2" />
              查询
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-16">ID</TableHead>
                <TableHead className="w-40">时间</TableHead>
                <TableHead className="w-24">用户</TableHead>
                <TableHead className="w-28">操作</TableHead>
                <TableHead className="w-32">IP / 来源</TableHead>
                <TableHead className="w-20">状态</TableHead>
                <TableHead>详情</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedLogs.map((log) => (
                <TableRow key={log.id}>
                  <TableCell className="text-muted-foreground">#{log.id}</TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {new Date(log.timestamp).toLocaleString('zh-CN')}
                  </TableCell>
                  <TableCell>
                    <span className="font-medium">{log.username}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="bg-primary/10 text-primary">
                      {log.action}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <code className="text-xs bg-muted px-2 py-1 rounded">
                      {log.ip_address}
                    </code>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={log.status === 'success' ? 'default' : 'destructive'}
                      className={
                        log.status === 'success'
                          ? 'bg-emerald-500/10 text-emerald-500'
                          : ''
                      }
                    >
                      {log.status === 'success' ? (
                        <CheckCircle className="w-3 h-3 mr-1" />
                      ) : (
                        <XCircle className="w-3 h-3 mr-1" />
                      )}
                      {log.status === 'success' ? '通过' : '拒绝'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground max-w-md truncate">
                    {log.details || '-'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {paginatedLogs.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              <Shield className="w-12 h-12 mx-auto mb-2 opacity-25" />
              暂无审计记录
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
              <div className="text-sm text-muted-foreground">
                共 {filteredLogs.length} 条记录 / 第 {currentPage} 页
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
