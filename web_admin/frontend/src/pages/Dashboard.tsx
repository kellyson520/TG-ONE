import { useEffect, useState } from 'react';
import { useAppStore } from '@/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Send,
  GitBranch,
  Filter,
  Activity,
  TrendingUp,
  Clock,
  Zap,
  ArrowRight,
  Plus,
  FileText,
  Settings,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

// Mock data for charts
const trafficData = [
  { name: '周一', value: 12000 },
  { name: '周二', value: 15234 },
  { name: '周三', value: 18900 },
  { name: '周四', value: 16500 },
  { name: '周五', value: 21000 },
  { name: '周六', value: 18500 },
  { name: '周日', value: 22300 },
];

const messageTypeData = [
  { name: '文本', value: 45, color: '#6366f1' },
  { name: '图片', value: 25, color: '#10b981' },
  { name: '视频', value: 15, color: '#f59e0b' },
  { name: '文件', value: 10, color: '#ef4444' },
  { name: '其他', value: 5, color: '#8b5cf6' },
];

const activityLogs = [
  { id: 1, message: '规则 #123 成功转发消息到目标群组', type: 'success', time: '2分钟前' },
  { id: 2, message: '检测到重复消息，已自动去重', type: 'info', time: '5分钟前' },
  { id: 3, message: '任务队列处理完成: 媒体下载 #456', type: 'success', time: '12分钟前' },
  { id: 4, message: '警告: 规则 #89 连接超时', type: 'warning', time: '15分钟前' },
  { id: 5, message: '用户 admin 登录系统', type: 'info', time: '20分钟前' },
];

export function Dashboard() {
  const { addNotification } = useAppStore();
  const [stats, setStats] = useState({
    todayForwards: 15234,
    activeRules: 24,
    dedupCache: 8932,
    errorRate: 0.32,
  });
  const [resources, setResources] = useState({
    cpu: 12.5,
    memory: 34.2,
    dbSize: 156.8,
  });

  // Simulate real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      setStats((prev) => ({
        ...prev,
        todayForwards: prev.todayForwards + Math.floor(Math.random() * 5),
        dedupCache: prev.dedupCache + Math.floor(Math.random() * 3),
      }));
      setResources({
        cpu: Math.max(5, Math.min(80, resources.cpu + (Math.random() - 0.5) * 10)),
        memory: Math.max(20, Math.min(70, resources.memory + (Math.random() - 0.5) * 5)),
        dbSize: resources.dbSize + 0.01,
      });
    }, 5000);
    return () => clearInterval(interval);
  }, [resources]);

  const statCards = [
    {
      title: '今日转发',
      value: stats.todayForwards.toLocaleString(),
      change: '+12%',
      icon: Send,
      color: 'primary',
      trend: 'up',
    },
    {
      title: '活跃规则',
      value: stats.activeRules.toString(),
      status: '稳定',
      icon: GitBranch,
      color: 'success',
    },
    {
      title: '去重缓存',
      value: stats.dedupCache.toLocaleString(),
      status: '去重中',
      icon: Filter,
      color: 'warning',
    },
    {
      title: '异常转发率',
      value: `${stats.errorRate.toFixed(2)}%`,
      icon: Activity,
      color: 'danger',
      alert: stats.errorRate > 1,
    },
  ];

  const quickActions = [
    { label: '新建规则', icon: Plus, href: '/rules', color: 'primary' },
    { label: '查看日志', icon: FileText, href: '/logs', color: 'secondary' },
    { label: '系统设置', icon: Settings, href: '/settings', color: 'secondary' },
  ];

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card, index) => (
          <Card
            key={card.title}
            className="relative overflow-hidden group hover:shadow-lg transition-all duration-300"
            style={{ animationDelay: `${index * 0.05}s` }}
          >
            <div
              className={`absolute top-0 left-0 w-1 h-full ${
                card.color === 'primary'
                  ? 'bg-primary'
                  : card.color === 'success'
                  ? 'bg-emerald-500'
                  : card.color === 'warning'
                  ? 'bg-amber-500'
                  : 'bg-red-500'
              }`}
            />
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-muted-foreground mb-1">{card.title}</p>
                  <p className="text-2xl font-bold">{card.value}</p>
                  {card.change && (
                    <p className="text-xs text-emerald-500 mt-1 flex items-center gap-1">
                      <TrendingUp className="w-3 h-3" />
                      {card.change}
                    </p>
                  )}
                  {card.status && (
                    <Badge variant="secondary" className="mt-1 text-xs">
                      {card.status}
                    </Badge>
                  )}
                  {card.alert && (
                    <Badge variant="destructive" className="mt-1 text-xs">
                      需要关注
                    </Badge>
                  )}
                </div>
                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    card.color === 'primary'
                      ? 'bg-primary/10 text-primary'
                      : card.color === 'success'
                      ? 'bg-emerald-500/10 text-emerald-500'
                      : card.color === 'warning'
                      ? 'bg-amber-500/10 text-amber-500'
                      : 'bg-red-500/10 text-red-500'
                  }`}
                >
                  <card.icon className="w-5 h-5" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Traffic Chart */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base font-medium">七日转发趋势</CardTitle>
            <Tabs defaultValue="volume" className="w-auto">
              <TabsList className="h-8">
                <TabsTrigger value="volume" className="text-xs px-3">
                  量级
                </TabsTrigger>
                <TabsTrigger value="rate" className="text-xs px-3">
                  成功率
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trafficData}>
                  <defs>
                    <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="name"
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                    tickLine={false}
                    tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#6366f1"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorValue)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Message Types */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">消息类型组成</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={messageTypeData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {messageTypeData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-2 gap-2 mt-4">
              {messageTypeData.map((item) => (
                <div key={item.name} className="flex items-center gap-2 text-xs">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-muted-foreground">{item.name}</span>
                  <span className="font-medium">{item.value}%</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-500" />
              快速操作
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {quickActions.map((action) => (
              <Button
                key={action.label}
                variant={action.color === 'primary' ? 'default' : 'outline'}
                className="w-full justify-between group"
                onClick={() =>
                  addNotification({
                    message: `正在跳转到${action.label}...`,
                    type: 'info',
                  })
                }
              >
                <div className="flex items-center gap-2">
                  <action.icon className="w-4 h-4" />
                  {action.label}
                </div>
                <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" />
              </Button>
            ))}
          </CardContent>
        </Card>

        {/* Resource Usage */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Activity className="w-4 h-4 text-primary" />
              资源利用率
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">CPU</span>
                <span className="font-medium">{resources.cpu.toFixed(1)}%</span>
              </div>
              <Progress value={resources.cpu} className="h-2" />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">内存</span>
                <span className="font-medium">{resources.memory.toFixed(1)}%</span>
              </div>
              <Progress value={resources.memory} className="h-2" />
            </div>
            <div className="pt-2 border-t border-border">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">数据库大小</span>
                <span className="font-medium">{resources.dbSize.toFixed(1)} MB</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Activity Log */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Clock className="w-4 h-4 text-info" />
              实时动态
            </CardTitle>
            <Button variant="ghost" size="sm" className="h-8 text-xs">
              刷新
            </Button>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-[200px] overflow-auto">
              {activityLogs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-start gap-3 text-sm p-2 rounded-lg hover:bg-muted/50 transition-colors"
                >
                  <div
                    className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${
                      log.type === 'success'
                        ? 'bg-emerald-500'
                        : log.type === 'warning'
                        ? 'bg-amber-500'
                        : 'bg-sky-500'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate">{log.message}</p>
                    <p className="text-xs text-muted-foreground">{log.time}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
