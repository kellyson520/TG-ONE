import { Outlet, useLocation } from 'react-router-dom';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { Toaster } from '@/components/ui/sonner';

const pageTitles: Record<string, { title: string; breadcrumb: string }> = {
  '/': { title: '仪表盘', breadcrumb: '系统概览' },
  '/rules': { title: '转发规则', breadcrumb: '配置管理' },
  '/visualization': { title: '拓扑可视化', breadcrumb: '配置管理' },
  '/history': { title: '转发历史', breadcrumb: '监控中心' },
  '/tasks': { title: '任务队列', breadcrumb: '监控中心' },
  '/downloads': { title: '媒体下载', breadcrumb: '监控中心' },
  '/logs': { title: '系统日志', breadcrumb: '监控中心' },
  '/archive': { title: '数据归档', breadcrumb: '监控中心' },
  '/audit-logs': { title: '审计日志', breadcrumb: '监控中心' },
  '/users': { title: '用户管理', breadcrumb: '系统管理' },
  '/security': { title: '安全中心', breadcrumb: '系统管理' },
  '/settings': { title: '系统设置', breadcrumb: '系统管理' },
};

export function Layout() {
  const { sidebarCollapsed } = useAppStore();
  const location = useLocation();
  const pageInfo = pageTitles[location.pathname] || { title: 'Forwarder Pro', breadcrumb: '' };

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div
        className={cn(
          'transition-all duration-300',
          sidebarCollapsed ? 'ml-16' : 'ml-64'
        )}
      >
        <Header title={pageInfo.title} breadcrumb={pageInfo.breadcrumb} />
        <main className="p-6">
          <div className="animate-fade-in">
            <Outlet />
          </div>
        </main>
      </div>
      <Toaster position="top-right" />
    </div>
  );
}
