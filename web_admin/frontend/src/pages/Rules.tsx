import { useState } from 'react';
import { useAppStore } from '@/store';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Plus,
  Search,
  MoreVertical,
  Edit,
  Play,
  Pause,
  Trash2,
  Download,
  Filter,
  ArrowRight,
} from 'lucide-react';
import type { Rule } from '@/types';

// Mock rules data
const mockRules: Rule[] = [
  {
    id: 1,
    source_chat_id: '-1001234567890',
    target_chat_id: '-1009876543210',
    source_chat: { title: '新闻源频道' },
    target_chat: { title: '聚合推送群' },
    enabled: true,
    enable_dedup: true,
    keywords_count: 5,
    replace_rules_count: 2,
    forwards: 15234,
    errors: 0,
  },
  {
    id: 2,
    source_chat_id: '-1002345678901',
    target_chat_id: '-1008765432109',
    source_chat: { title: '技术讨论组' },
    target_chat: { title: '技术归档' },
    enabled: true,
    enable_dedup: true,
    keywords_count: 3,
    replace_rules_count: 0,
    forwards: 8921,
    errors: 2,
  },
  {
    id: 3,
    source_chat_id: '-1003456789012',
    target_chat_id: '-1007654321098',
    source_chat: { title: '监控告警' },
    target_chat: { title: '值班群' },
    enabled: false,
    enable_dedup: false,
    keywords_count: 8,
    replace_rules_count: 5,
    forwards: 3456,
    errors: 12,
  },
  {
    id: 4,
    source_chat_id: '-1004567890123',
    target_chat_id: '-1006543210987',
    source_chat: { title: '产品更新' },
    target_chat: { title: '用户通知' },
    enabled: true,
    enable_dedup: true,
    keywords_count: 2,
    replace_rules_count: 1,
    forwards: 5678,
    errors: 0,
  },
  {
    id: 5,
    source_chat_id: '-1005678901234',
    target_chat_id: '-1005432109876',
    source_chat: { title: '内部公告' },
    target_chat: { title: '全员群' },
    enabled: true,
    enable_dedup: true,
    keywords_count: 0,
    replace_rules_count: 0,
    forwards: 1234,
    errors: 1,
  },
];

export function Rules() {
  const { addNotification } = useAppStore();
  const [rules, setRules] = useState<Rule[]>(mockRules);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'enabled' | 'disabled'>('all');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    sourceChat: '',
    targetChat: '',
    keywords: '',
    enabled: true,
    enableDedup: true,
  });

  const filteredRules = rules.filter((rule) => {
    const matchesSearch =
      searchQuery === '' ||
      rule.source_chat?.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rule.target_chat?.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rule.source_chat_id.includes(searchQuery);
    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'enabled' ? rule.enabled : !rule.enabled);
    return matchesSearch && matchesStatus;
  });

  const stats = {
    total: rules.length,
    enabled: rules.filter((r) => r.enabled).length,
    disabled: rules.filter((r) => !r.enabled).length,
    todayForwards: rules.reduce((sum, r) => sum + (r.forwards || 0), 0),
  };

  const handleCreateRule = () => {
    const newRule: Rule = {
      id: Date.now(),
      source_chat_id: formData.sourceChat,
      target_chat_id: formData.targetChat,
      source_chat: { title: formData.sourceChat },
      target_chat: { title: formData.targetChat },
      enabled: formData.enabled,
      enable_dedup: formData.enableDedup,
      keywords_count: formData.keywords.split(',').filter((k) => k.trim()).length,
      replace_rules_count: 0,
      forwards: 0,
      errors: 0,
    };
    setRules([...rules, newRule]);
    setIsCreateDialogOpen(false);
    setFormData({ sourceChat: '', targetChat: '', keywords: '', enabled: true, enableDedup: true });
    addNotification({ message: '规则创建成功', type: 'success' });
  };

  const handleUpdateRule = () => {
    if (!editingRule) return;
    setRules(
      rules.map((r) =>
        r.id === editingRule.id
          ? {
              ...r,
              source_chat_id: formData.sourceChat,
              target_chat_id: formData.targetChat,
              source_chat: { title: formData.sourceChat },
              target_chat: { title: formData.targetChat },
              enabled: formData.enabled,
              enable_dedup: formData.enableDedup,
              keywords_count: formData.keywords.split(',').filter((k) => k.trim()).length,
            }
          : r
      )
    );
    setEditingRule(null);
    addNotification({ message: '规则更新成功', type: 'success' });
  };

  const handleToggleRule = (id: number) => {
    setRules(
      rules.map((r) =>
        r.id === id ? { ...r, enabled: !r.enabled } : r
      )
    );
    addNotification({ message: '规则状态已更新', type: 'info' });
  };

  const handleDeleteRule = (id: number) => {
    setRules(rules.filter((r) => r.id !== id));
    addNotification({ message: '规则已删除', type: 'success' });
  };

  const openEditDialog = (rule: Rule) => {
    setEditingRule(rule);
    setFormData({
      sourceChat: rule.source_chat_id,
      targetChat: rule.target_chat_id,
      keywords: '',
      enabled: rule.enabled,
      enableDedup: rule.enable_dedup,
    });
  };

  const exportRules = () => {
    const dataStr = JSON.stringify(rules, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    const exportFileDefaultName = `forwarder_rules_${new Date().toISOString().split('T')[0]}.json`;
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
    addNotification({ message: '规则已导出', type: 'success' });
  };

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: '总规则', value: stats.total, color: 'primary' },
          { label: '已启用', value: stats.enabled, color: 'success' },
          { label: '已禁用', value: stats.disabled, color: 'warning' },
          { label: '今日转发', value: stats.todayForwards.toLocaleString(), color: 'info' },
        ].map((stat) => (
          <Card key={stat.label} className="metric-card">
            <div className={`metric-label text-${stat.color}`}>{stat.label}</div>
            <div className="metric-value">{stat.value}</div>
          </Card>
        ))}
      </div>

      {/* Toolbar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3 flex-1">
              <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
                <DialogTrigger asChild>
                  <Button className="gradient-primary">
                    <Plus className="w-4 h-4 mr-2" />
                    新建规则
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-lg">
                  <DialogHeader>
                    <DialogTitle>创建转发规则</DialogTitle>
                    <DialogDescription>
                      配置消息转发规则，支持关键词过滤和智能去重
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label>来源聊天 ID</Label>
                      <Input
                        placeholder="-123456789"
                        value={formData.sourceChat}
                        onChange={(e) => setFormData({ ...formData, sourceChat: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>目标聊天 ID</Label>
                      <Input
                        placeholder="-987654321"
                        value={formData.targetChat}
                        onChange={(e) => setFormData({ ...formData, targetChat: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>关键词（逗号分隔）</Label>
                      <Textarea
                        placeholder="关键词1, 关键词2..."
                        value={formData.keywords}
                        onChange={(e) => setFormData({ ...formData, keywords: e.target.value })}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Switch
                          checked={formData.enabled}
                          onCheckedChange={(checked) =>
                            setFormData({ ...formData, enabled: checked })
                          }
                        />
                        <Label className="font-normal">立即启用</Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Switch
                          checked={formData.enableDedup}
                          onCheckedChange={(checked) =>
                            setFormData({ ...formData, enableDedup: checked })
                          }
                        />
                        <Label className="font-normal">智能去重</Label>
                      </div>
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                      取消
                    </Button>
                    <Button onClick={handleCreateRule} className="gradient-primary">
                      保存规则
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>

              <div className="relative flex-1 max-w-sm">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="搜索规则..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <select
                className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as any)}
              >
                <option value="all">所有状态</option>
                <option value="enabled">启用</option>
                <option value="disabled">禁用</option>
              </select>
              <Button variant="outline" size="icon" onClick={exportRules}>
                <Download className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Rules Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filteredRules.map((rule, index) => (
          <Card
            key={rule.id}
            className="group hover:shadow-lg transition-all duration-300"
            style={{ animationDelay: `${index * 0.05}s` }}
          >
            <CardContent className="p-5">
              <div className="flex items-start justify-between mb-4">
                <Badge
                  variant={rule.enabled ? 'default' : 'secondary'}
                  className={rule.enabled ? 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20' : ''}
                >
                  {rule.enabled ? '转发中' : '已暂停'}
                </Badge>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <MoreVertical className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => openEditDialog(rule)}>
                      <Edit className="w-4 h-4 mr-2" />
                      编辑
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleToggleRule(rule.id)}>
                      {rule.enabled ? (
                        <>
                          <Pause className="w-4 h-4 mr-2" />
                          暂停
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4 mr-2" />
                          启用
                        </>
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-red-500"
                      onClick={() => handleDeleteRule(rule.id)}
                    >
                      <Trash2 className="w-4 h-4 mr-2" />
                      删除
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              <div className="space-y-4">
                <div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
                    数据路由
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">
                        {rule.source_chat?.title || rule.source_chat_id}
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-primary flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">
                        {rule.target_chat?.title || rule.target_chat_id}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4 pt-4 border-t border-border">
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">递送量</div>
                    <div className="font-semibold">{(rule.forwards || 0).toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">关键词</div>
                    <div className="font-semibold">{rule.keywords_count || 0}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">异常</div>
                    <div className={`font-semibold ${rule.errors && rule.errors > 0 ? 'text-red-500' : 'text-emerald-500'}`}>
                      {rule.errors || 0}
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {filteredRules.length === 0 && (
        <div className="text-center py-12">
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
            <Filter className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-medium mb-2">没有找到规则</h3>
          <p className="text-muted-foreground">尝试调整搜索条件或创建新规则</p>
        </div>
      )}

      {/* Edit Dialog */}
      <Dialog open={!!editingRule} onOpenChange={() => setEditingRule(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>编辑转发规则</DialogTitle>
            <DialogDescription>修改规则配置</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>来源聊天 ID</Label>
              <Input
                value={formData.sourceChat}
                onChange={(e) => setFormData({ ...formData, sourceChat: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>目标聊天 ID</Label>
              <Input
                value={formData.targetChat}
                onChange={(e) => setFormData({ ...formData, targetChat: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>关键词（逗号分隔）</Label>
              <Textarea
                placeholder="关键词1, 关键词2..."
                value={formData.keywords}
                onChange={(e) => setFormData({ ...formData, keywords: e.target.value })}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Switch
                  checked={formData.enabled}
                  onCheckedChange={(checked) => setFormData({ ...formData, enabled: checked })}
                />
                <Label className="font-normal">启用规则</Label>
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  checked={formData.enableDedup}
                  onCheckedChange={(checked) => setFormData({ ...formData, enableDedup: checked })}
                />
                <Label className="font-normal">智能去重</Label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingRule(null)}>
              取消
            </Button>
            <Button onClick={handleUpdateRule} className="gradient-primary">
              保存更改
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
