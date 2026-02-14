import { useState } from 'react';
import { useAppStore } from '@/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Save,
  RefreshCw,
  Database,
  Server,
  Bell,
  Shield,
} from 'lucide-react';

interface SettingGroup {
  name: string;
  icon: React.ElementType;
  settings: {
    key: string;
    label: string;
    type: 'string' | 'number' | 'boolean' | 'select';
    value: any;
    options?: string[];
    requiresRestart?: boolean;
    sensitive?: boolean;
    description?: string;
  }[];
}

const settingGroups: SettingGroup[] = [
  {
    name: '数据库',
    icon: Database,
    settings: [
      {
        key: 'db_pool_size',
        label: '连接池大小',
        type: 'number',
        value: 10,
        requiresRestart: true,
        description: '数据库连接池的最大连接数',
      },
      {
        key: 'db_timeout',
        label: '连接超时',
        type: 'number',
        value: 30,
        description: '数据库连接超时时间（秒）',
      },
    ],
  },
  {
    name: '转发服务',
    icon: Server,
    settings: [
      {
        key: 'forward_interval',
        label: '转发间隔',
        type: 'number',
        value: 5,
        description: '消息转发检查间隔（秒）',
      },
      {
        key: 'max_retry',
        label: '最大重试次数',
        type: 'number',
        value: 3,
        description: '转发失败时的最大重试次数',
      },
      {
        key: 'dedup_enabled',
        label: '启用去重',
        type: 'boolean',
        value: true,
        description: '自动检测并过滤重复消息',
      },
      {
        key: 'dedup_ttl',
        label: '去重缓存时间',
        type: 'number',
        value: 86400,
        description: '去重指纹缓存时间（秒）',
      },
    ],
  },
  {
    name: '通知',
    icon: Bell,
    settings: [
      {
        key: 'notify_errors',
        label: '错误通知',
        type: 'boolean',
        value: true,
        description: '发生错误时发送通知',
      },
      {
        key: 'notify_webhook',
        label: 'Webhook URL',
        type: 'string',
        value: '',
        sensitive: true,
        description: '接收通知的 Webhook 地址',
      },
    ],
  },
  {
    name: '安全',
    icon: Shield,
    settings: [
      {
        key: 'session_timeout',
        label: '会话超时',
        type: 'number',
        value: 3600,
        description: '用户会话超时时间（秒）',
      },
      {
        key: 'max_login_attempts',
        label: '最大登录尝试',
        type: 'number',
        value: 5,
        description: '登录失败锁定前的最大尝试次数',
      },
      {
        key: 'require_2fa',
        label: '强制 2FA',
        type: 'boolean',
        value: false,
        requiresRestart: true,
        description: '要求所有用户启用双重验证',
      },
    ],
  },
];

export function Settings() {
  const { addNotification } = useAppStore();
  const [settings, setSettings] = useState(settingGroups);
  const [isSaving, setIsSaving] = useState(false);
  const [changedKeys, setChangedKeys] = useState<Set<string>>(new Set());

  const handleSettingChange = (groupIndex: number, settingIndex: number, value: any) => {
    const newSettings = [...settings];
    const setting = newSettings[groupIndex].settings[settingIndex];
    setting.value = value;
    setSettings(newSettings);
    setChangedKeys(new Set(changedKeys).add(setting.key));
  };

  const handleSave = async () => {
    setIsSaving(true);
    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsSaving(false);
    setChangedKeys(new Set());
    addNotification({ message: '设置已保存', type: 'success' });
  };

  const handleRefresh = () => {
    addNotification({ message: '设置已刷新', type: 'info' });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">系统设置</h2>
          <p className="text-muted-foreground">配置系统各项参数</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleRefresh}>
            <RefreshCw className="w-4 h-4 mr-2" />
            刷新
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving || changedKeys.size === 0}
            className="gradient-primary"
          >
            {isSaving ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            保存更改
          </Button>
        </div>
      </div>

      {/* Settings Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {settings.map((group, groupIndex) => (
          <Card key={group.name}>
            <CardHeader>
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <group.icon className="w-4 h-4 text-primary" />
                {group.name}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {group.settings.map((setting, settingIndex) => (
                <div key={setting.key} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="flex items-center gap-2">
                      {setting.label}
                      {setting.requiresRestart && (
                        <Badge variant="secondary" className="text-[10px]">
                          需重启
                        </Badge>
                      )}
                      {changedKeys.has(setting.key) && (
                        <Badge variant="secondary" className="bg-amber-500/10 text-amber-500 text-[10px]">
                          已修改
                        </Badge>
                      )}
                    </Label>
                  </div>
                  {setting.type === 'boolean' ? (
                    <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                      <span className="text-sm text-muted-foreground">
                        {setting.description}
                      </span>
                      <Switch
                        checked={setting.value}
                        onCheckedChange={(checked) =>
                          handleSettingChange(groupIndex, settingIndex, checked)
                        }
                      />
                    </div>
                  ) : setting.type === 'select' ? (
                    <Select
                      value={setting.value}
                      onValueChange={(value) =>
                        handleSettingChange(groupIndex, settingIndex, value)
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {setting.options?.map((option) => (
                          <SelectItem key={option} value={option}>
                            {option}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <div className="space-y-1">
                      <Input
                        type={setting.type === 'number' ? 'number' : 'text'}
                        value={setting.value}
                        onChange={(e) =>
                          handleSettingChange(
                            groupIndex,
                            settingIndex,
                            setting.type === 'number'
                              ? parseInt(e.target.value)
                              : e.target.value
                          )
                        }
                        placeholder={setting.sensitive ? '••••••••' : ''}
                      />
                      {setting.description && (
                        <p className="text-xs text-muted-foreground">
                          {setting.description}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
