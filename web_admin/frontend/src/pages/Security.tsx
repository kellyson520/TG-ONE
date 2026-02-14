import { useState } from 'react';
import { useAppStore } from '@/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Shield,
  QrCode,
  Copy,
  CheckCircle,
  Plus,
  Trash2,
  Lock,
  Unlock,
} from 'lucide-react';
import type { ACLRule } from '@/types';

// Mock ACL rules
const mockAclRules: ACLRule[] = [
  { ip_address: '192.168.1.0/24', type: 'ALLOW', reason: '内网访问' },
  { ip_address: '10.0.0.0/8', type: 'ALLOW', reason: 'VPN 网络' },
  { ip_address: '1.2.3.4', type: 'BLOCK', reason: '恶意攻击' },
];

export function Security() {
  const { addNotification } = useAppStore();
  const [is2FAEnabled, setIs2FAEnabled] = useState(false);
  const [isSettingUp2FA, setIsSettingUp2FA] = useState(false);
  const [twoFactorCode, setTwoFactorCode] = useState('');
  const [aclRules, setAclRules] = useState<ACLRule[]>(mockAclRules);
  const [isAddAclDialogOpen, setIsAddAclDialogOpen] = useState(false);
  const [newAclRule, setNewAclRule] = useState<Partial<ACLRule>>({
    type: 'ALLOW',
  });

  const handleSetup2FA = () => {
    setIsSettingUp2FA(true);
  };

  const handleConfirm2FA = () => {
    if (twoFactorCode.length === 6) {
      setIs2FAEnabled(true);
      setIsSettingUp2FA(false);
      addNotification({ message: '2FA 已成功启用', type: 'success' });
    } else {
      addNotification({ message: '请输入有效的 6 位验证码', type: 'error' });
    }
  };

  const handleDisable2FA = () => {
    if (confirm('禁用 2FA 将降低账户安全性，确定继续？')) {
      setIs2FAEnabled(false);
      addNotification({ message: '2FA 已禁用', type: 'info' });
    }
  };

  const handleAddAclRule = () => {
    if (!newAclRule.ip_address) {
      addNotification({ message: '请输入 IP 地址', type: 'error' });
      return;
    }
    setAclRules([...aclRules, newAclRule as ACLRule]);
    setIsAddAclDialogOpen(false);
    setNewAclRule({ type: 'ALLOW' });
    addNotification({ message: 'ACL 规则已添加', type: 'success' });
  };

  const handleDeleteAclRule = (ip: string) => {
    setAclRules(aclRules.filter((r) => r.ip_address !== ip));
    addNotification({ message: 'ACL 规则已删除', type: 'info' });
  };

  const copySecret = () => {
    navigator.clipboard.writeText('JBSWY3DPEHPK3PXP');
    addNotification({ message: '密钥已复制到剪贴板', type: 'success' });
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 2FA Section */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Shield className="w-4 h-4 text-primary" />
              2FA 双重身份验证
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!is2FAEnabled && !isSettingUp2FA && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  通过 TOTP 协议为您的账户增加一层安全防护。在您输入密码后，仍需提供动态验证码方可进入系统。
                </p>
                <Button onClick={handleSetup2FA} className="w-full gradient-primary">
                  <QrCode className="w-4 h-4 mr-2" />
                  立即开启安全加固
                </Button>
              </div>
            )}

            {!is2FAEnabled && isSettingUp2FA && (
              <div className="space-y-6">
                <div className="p-4 bg-muted rounded-lg text-center">
                  <div className="text-sm font-medium mb-3">#1 扫描此二维码</div>
                  <div className="bg-white p-4 rounded-lg inline-block mb-3">
                    {/* Placeholder QR code */}
                    <div className="w-40 h-40 bg-gradient-to-br from-primary/20 to-purple-500/20 flex items-center justify-center">
                      <QrCode className="w-24 h-24 text-primary" />
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Input
                      value="JBSWY3DPEHPK3PXP"
                      readOnly
                      className="text-center font-mono"
                    />
                    <Button variant="outline" size="icon" onClick={copySecret}>
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                <div className="p-4 bg-muted rounded-lg">
                  <div className="text-sm font-medium mb-3">#2 输入验证码</div>
                  <div className="flex items-center gap-2">
                    <Input
                      placeholder="000000"
                      maxLength={6}
                      value={twoFactorCode}
                      onChange={(e) => setTwoFactorCode(e.target.value)}
                      className="text-center text-2xl tracking-[0.5em] font-mono"
                    />
                    <Button onClick={handleConfirm2FA} className="gradient-primary">
                      激活
                    </Button>
                  </div>
                </div>

                <Button variant="ghost" className="w-full" onClick={() => setIsSettingUp2FA(false)}>
                  放弃设置
                </Button>
              </div>
            )}

            {is2FAEnabled && (
              <div className="space-y-4">
                <div className="p-4 bg-emerald-500/10 rounded-lg flex items-center gap-3">
                  <CheckCircle className="w-8 h-8 text-emerald-500" />
                  <div>
                    <div className="font-medium">双重验证已启用</div>
                    <div className="text-sm text-muted-foreground">
                      您的账户当前安全性极高
                    </div>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">
                  如果您遗失了认证设备，请联系管理员协助重置。您也可以随时关闭此功能（不建议）。
                </p>
                <Button
                  variant="outline"
                  className="w-full text-red-500 hover:text-red-600"
                  onClick={handleDisable2FA}
                >
                  <Unlock className="w-4 h-4 mr-2" />
                  禁用安全令牌
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* IP ACL Section */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Lock className="w-4 h-4 text-amber-500" />
              IP 访问控制
            </CardTitle>
            <Dialog open={isAddAclDialogOpen} onOpenChange={setIsAddAclDialogOpen}>
              <DialogTrigger asChild>
                <Button size="sm" className="gradient-primary">
                  <Plus className="w-4 h-4 mr-1" />
                  添加规则
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>添加授权规则</DialogTitle>
                  <DialogDescription>
                    支持 IP 地址或 CIDR 格式（如 192.168.0.0/24）
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label>IP 或 CIDR</Label>
                    <Input
                      placeholder="例如: 1.2.3.4 或 192.168.0.0/24"
                      value={newAclRule.ip_address || ''}
                      onChange={(e) =>
                        setNewAclRule({ ...newAclRule, ip_address: e.target.value })
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>访问策略</Label>
                    <select
                      className="w-full h-9 rounded-md border border-input bg-background px-3"
                      value={newAclRule.type}
                      onChange={(e) =>
                        setNewAclRule({ ...newAclRule, type: e.target.value as 'ALLOW' | 'BLOCK' })
                      }
                    >
                      <option value="ALLOW">白名单 (允许)</option>
                      <option value="BLOCK">黑名单 (阻止)</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label>描述</Label>
                    <Input
                      placeholder="简述该规则用途"
                      value={newAclRule.reason || ''}
                      onChange={(e) =>
                        setNewAclRule({ ...newAclRule, reason: e.target.value })
                      }
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setIsAddAclDialogOpen(false)}>
                    取消
                  </Button>
                  <Button onClick={handleAddAclRule} className="gradient-primary">
                    保存规则
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              精准限制允许登录系统的 IP 范围。支持 CIDR 格式。黑名单策略优于白名单。
            </p>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>来源地址</TableHead>
                  <TableHead>策略</TableHead>
                  <TableHead>理由</TableHead>
                  <TableHead className="w-16"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {aclRules.map((rule) => (
                  <TableRow key={rule.ip_address}>
                    <TableCell className="font-mono">{rule.ip_address}</TableCell>
                    <TableCell>
                      <Badge
                        variant={rule.type === 'ALLOW' ? 'default' : 'destructive'}
                        className={
                          rule.type === 'ALLOW'
                            ? 'bg-emerald-500/10 text-emerald-500'
                            : ''
                        }
                      >
                        {rule.type === 'ALLOW' ? '允许' : '阻止'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {rule.reason || '-'}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-red-500"
                        onClick={() => handleDeleteAclRule(rule.ip_address)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
