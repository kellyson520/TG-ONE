import { useState } from 'react';
import { useAppStore } from '@/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
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
  ShieldCheck,
  UserX,
  Trash2,
  RefreshCw,
  Users as UsersIcon,
  Info,
} from 'lucide-react';
import type { User as UserType } from '@/types';

// Mock users data
const mockUsers: UserType[] = [
  {
    id: 1,
    username: 'admin',
    email: 'admin@forwarder.pro',
    is_admin: true,
    is_active: true,
    login_count: 156,
    last_login: '2024-01-15T10:30:00Z',
  },
  {
    id: 2,
    username: 'operator1',
    email: 'op1@company.com',
    is_admin: false,
    is_active: true,
    login_count: 45,
    last_login: '2024-01-14T16:20:00Z',
  },
  {
    id: 3,
    username: 'operator2',
    email: 'op2@company.com',
    is_admin: false,
    is_active: true,
    login_count: 23,
    last_login: '2024-01-13T09:15:00Z',
  },
  {
    id: 4,
    username: 'viewer',
    email: 'viewer@company.com',
    is_admin: false,
    is_active: false,
    login_count: 5,
    last_login: '2024-01-01T11:00:00Z',
  },
];

export function Users() {
  const { addNotification } = useAppStore();
  const [users, setUsers] = useState<UserType[]>(mockUsers);
  const [allowRegistration, setAllowRegistration] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleToggleAdmin = (id: number) => {
    setUsers(
      users.map((u) =>
        u.id === id ? { ...u, is_admin: !u.is_admin } : u
      )
    );
    addNotification({ message: '用户权限已更新', type: 'success' });
  };

  const handleToggleActive = (id: number) => {
    setUsers(
      users.map((u) =>
        u.id === id ? { ...u, is_active: !u.is_active } : u
      )
    );
    addNotification({ message: '用户状态已更新', type: 'info' });
  };

  const handleDeleteUser = (id: number) => {
    if (confirm('确定要删除此用户吗？此操作不可撤销。')) {
      setUsers(users.filter((u) => u.id !== id));
      addNotification({ message: '用户已删除', type: 'success' });
    }
  };

  const handleSaveSettings = () => {
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      addNotification({ message: '设置已保存', type: 'success' });
    }, 1000);
  };

  const refreshUsers = () => {
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      addNotification({ message: '用户列表已刷新', type: 'info' });
    }, 500);
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Access Control Settings */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Shield className="w-4 h-4 text-primary" />
              访问控制
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="p-4 rounded-lg bg-muted/50">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium">开放注册</div>
                  <div className="text-sm text-muted-foreground">
                    允许新用户自行创建账号
                  </div>
                </div>
                <Switch
                  checked={allowRegistration}
                  onCheckedChange={setAllowRegistration}
                />
              </div>
            </div>

            <Alert className="bg-sky-500/10 border-sky-500/20">
              <Info className="w-4 h-4 text-sky-500" />
              <AlertDescription className="text-sm">
                管理员始终拥有最高权限，请谨慎操作。
              </AlertDescription>
            </Alert>

            <Button
              onClick={handleSaveSettings}
              className="w-full gradient-primary"
              disabled={isLoading}
            >
              {isLoading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
              ) : null}
              保存全局配置
            </Button>
          </CardContent>
        </Card>

        {/* Users List */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <UsersIcon className="w-4 h-4 text-primary" />
                用户列表
              </CardTitle>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={refreshUsers}
              disabled={isLoading}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
              刷新
            </Button>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>用户信息</TableHead>
                  <TableHead>角色</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>近期活动</TableHead>
                  <TableHead className="text-right">管理</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                          <span className="text-sm font-medium text-primary">
                            {user.username[0].toUpperCase()}
                          </span>
                        </div>
                        <div>
                          <div className="font-medium">{user.username}</div>
                          <div className="text-xs text-muted-foreground">
                            {user.email || '未绑定邮箱'}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={user.is_admin ? 'default' : 'secondary'}
                        className={
                          user.is_admin
                            ? 'bg-primary/10 text-primary hover:bg-primary/20'
                            : ''
                        }
                      >
                        {user.is_admin ? (
                          <>
                            <ShieldCheck className="w-3 h-3 mr-1" />
                            管理员
                          </>
                        ) : (
                          '普通成员'
                        )}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={user.is_active ? 'default' : 'destructive'}
                        className={
                          user.is_active
                            ? 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20'
                            : ''
                        }
                      >
                        {user.is_active ? '正常' : '已锁定'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        登录 {user.login_count} 次
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {user.last_login
                          ? new Date(user.last_login).toLocaleDateString('zh-CN')
                          : '从未登录'}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => handleToggleAdmin(user.id)}
                          title={user.is_admin ? '撤销管理员' : '设为管理员'}
                        >
                          <ShieldCheck
                            className={`w-4 h-4 ${
                              user.is_admin ? 'text-primary' : 'text-muted-foreground'
                            }`}
                          />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => handleToggleActive(user.id)}
                          title={user.is_active ? '锁定账户' : '解锁账户'}
                        >
                          <UserX
                            className={`w-4 h-4 ${
                              user.is_active ? 'text-muted-foreground' : 'text-red-500'
                            }`}
                          />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-500 hover:text-red-600"
                          onClick={() => handleDeleteUser(user.id)}
                          title="删除用户"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
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
