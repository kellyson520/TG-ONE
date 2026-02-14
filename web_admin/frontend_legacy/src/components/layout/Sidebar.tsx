import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  GitBranch,
  Share2,
  History,
  Zap,
  CloudDownload,
  FileText,
  Archive,
  Shield,
  Users,
  Lock,
  Settings,
  ChevronLeft,
  ChevronRight,
  Send,
  LogOut,
  ChevronDown,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface NavItem {
  label: string;
  path: string;
  icon: React.ElementType;
  category?: string;
}

const navItems: NavItem[] = [
  { label: '仪表盘', path: '/', icon: LayoutDashboard, category: '工作区' },
  { label: '转发规则', path: '/rules', icon: GitBranch, category: '配置' },
  { label: '拓扑可视化', path: '/visualization', icon: Share2, category: '配置' },
  { label: '转发历史', path: '/history', icon: History, category: '监控' },
  { label: '任务队列', path: '/tasks', icon: Zap, category: '监控' },
  { label: '媒体下载', path: '/downloads', icon: CloudDownload, category: '监控' },
  { label: '系统日志', path: '/logs', icon: FileText, category: '监控' },
  { label: '数据归档', path: '/archive', icon: Archive, category: '监控' },
  { label: '审计日志', path: '/audit-logs', icon: Shield, category: '监控' },
  { label: '用户管理', path: '/users', icon: Users, category: '系统' },
  { label: '安全中心', path: '/security', icon: Lock, category: '系统' },
  { label: '系统设置', path: '/settings', icon: Settings, category: '系统' },
];

const categories = ['工作区', '配置', '监控', '系统'];

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, theme, toggleTheme } = useAppStore();
  const location = useLocation();
  const [expandedCategories, setExpandedCategories] = useState<string[]>(categories);

  const toggleCategory = (category: string) => {
    setExpandedCategories((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category]
    );
  };

  const groupedItems = categories.map((category) => ({
    category,
    items: navItems.filter((item) => item.category === category),
  }));

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          'fixed left-0 top-0 h-screen bg-card border-r border-border flex flex-col transition-all duration-300 z-50',
          sidebarCollapsed ? 'w-16' : 'w-64'
        )}
      >
        {/* Logo */}
        <div className="h-16 flex items-center px-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg gradient-primary flex items-center justify-center flex-shrink-0">
              <Send className="w-4 h-4 text-white" />
            </div>
            {!sidebarCollapsed && (
              <div className="font-semibold text-lg">
                Forwarder<span className="text-primary">Pro</span>
              </div>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4 px-2">
          {groupedItems.map(({ category, items }) => (
            <div key={category} className="mb-2">
              {!sidebarCollapsed && (
                <button
                  onClick={() => toggleCategory(category)}
                  className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider hover:text-foreground transition-colors"
                >
                  {category}
                  <ChevronDown
                    className={cn(
                      'w-3 h-3 transition-transform',
                      !expandedCategories.includes(category) && '-rotate-90'
                    )}
                  />
                </button>
              )}
              {expandedCategories.includes(category) && (
                <div className="space-y-0.5 mt-1">
                  {items.map((item) => {
                    const isActive = location.pathname === item.path;
                    const Icon = item.icon;

                    if (sidebarCollapsed) {
                      return (
                        <Tooltip key={item.path}>
                          <TooltipTrigger asChild>
                            <NavLink
                              to={item.path}
                              className={cn(
                                'flex items-center justify-center p-2.5 rounded-lg transition-all duration-200',
                                isActive
                                  ? 'bg-primary/10 text-primary'
                                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                              )}
                            >
                              <Icon className="w-5 h-5" />
                            </NavLink>
                          </TooltipTrigger>
                          <TooltipContent side="right">
                            <p>{item.label}</p>
                          </TooltipContent>
                        </Tooltip>
                      );
                    }

                    return (
                      <NavLink
                        key={item.path}
                        to={item.path}
                        className={cn(
                          'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200',
                          isActive
                            ? 'bg-primary/10 text-primary'
                            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                        )}
                      >
                        <Icon className="w-4 h-4" />
                        {item.label}
                      </NavLink>
                    );
                  })}
                </div>
              )}
            </div>
          ))}
        </nav>

        {/* Bottom Actions */}
        <div className="p-2 border-t border-border space-y-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={toggleTheme}
                className="w-full flex items-center justify-center p-2.5 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-all"
              >
                {theme === 'dark' ? (
                  <div className="w-5 h-5 flex items-center justify-center">☀️</div>
                ) : (
                  <div className="w-5 h-5 flex items-center justify-center">🌙</div>
                )}
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <p>切换主题</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={toggleSidebar}
                className="w-full flex items-center justify-center p-2.5 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-all"
              >
                {sidebarCollapsed ? (
                  <ChevronRight className="w-5 h-5" />
                ) : (
                  <ChevronLeft className="w-5 h-5" />
                )}
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <p>{sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}</p>
            </TooltipContent>
          </Tooltip>

          {!sidebarCollapsed && (
            <div className="mt-4 p-3 rounded-lg bg-muted/50">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                  <span className="text-xs font-medium text-primary">RA</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">Root Admin</p>
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                    在线
                  </p>
                </div>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <LogOut className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </div>
      </aside>
    </TooltipProvider>
  );
}
