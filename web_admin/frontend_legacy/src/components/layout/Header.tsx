import { useState, useEffect } from 'react';
import { useAppStore } from '@/store';
import { Cpu, MemoryStick, Bell, Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';

interface HeaderProps {
  title: string;
  breadcrumb?: string;
}

interface Notification {
  id: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
}

export function Header({ title, breadcrumb }: HeaderProps) {
  const { toggleSidebar, notifications } = useAppStore();
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Simulate system metrics
  const [metrics, setMetrics] = useState({ cpu: 12, memory: 34 });
  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics({
        cpu: Math.floor(Math.random() * 30) + 5,
        memory: Math.floor(Math.random() * 20) + 25,
      });
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-16 border-b border-border bg-card/50 backdrop-blur-xl flex items-center justify-between px-6 sticky top-0 z-40">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={toggleSidebar}
        >
          <Menu className="w-5 h-5" />
        </Button>
        <div>
          {breadcrumb && (
            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-0.5">
              {breadcrumb}
            </div>
          )}
          <h1 className="text-lg font-semibold">{title}</h1>
        </div>
      </div>

      <div className="flex items-center gap-6">
        {/* System Metrics */}
        <div className="hidden md:flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm">
            <Cpu className="w-4 h-4 text-primary" />
            <span className="text-muted-foreground">CPU</span>
            <span className="font-mono font-medium">{metrics.cpu}%</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <MemoryStick className="w-4 h-4 text-info" />
            <span className="text-muted-foreground">内存</span>
            <span className="font-mono font-medium">{metrics.memory}%</span>
          </div>
        </div>

        <div className="h-6 w-px bg-border hidden md:block" />

        {/* Time */}
        <div className="hidden sm:block text-sm text-muted-foreground font-mono">
          {currentTime.toLocaleTimeString('zh-CN', { hour12: false })}
        </div>

        {/* Notifications */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="w-5 h-5" />
              {notifications.length > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-primary text-primary-foreground text-[10px] font-medium rounded-full flex items-center justify-center">
                  {notifications.length}
                </span>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-80">
            <DropdownMenuLabel>通知</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {notifications.length === 0 ? (
              <div className="py-4 text-center text-sm text-muted-foreground">
                暂无通知
              </div>
            ) : (
              notifications.map((notification: Notification) => (
                <DropdownMenuItem key={notification.id} className="flex flex-col items-start gap-1">
                  <span className="text-sm">{notification.message}</span>
                  <Badge
                    variant={
                      notification.type === 'error'
                        ? 'destructive'
                        : notification.type === 'success'
                        ? 'default'
                        : 'secondary'
                    }
                    className="text-[10px]"
                  >
                    {notification.type}
                  </Badge>
                </DropdownMenuItem>
              ))
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
