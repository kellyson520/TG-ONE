import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Send, Eye, EyeOff, Shield, Lock, User } from 'lucide-react';

export function Login() {
  const navigate = useNavigate();
  const { setAuthenticated, addNotification } = useAppStore();
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [step, setStep] = useState<'credentials' | '2fa'>('credentials');
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    remember: false,
    twoFactorCode: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1000));

    if (step === 'credentials') {
      // Simulate 2FA requirement
      if (formData.username === 'admin') {
        setStep('2fa');
        setIsLoading(false);
        return;
      }
    }

    setAuthenticated(true);
    addNotification({
      message: '登录成功，欢迎回来！',
      type: 'success',
    });
    navigate('/');
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-background">
      {/* Background effects */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-1/2 -right-1/2 w-[800px] h-[800px] rounded-full bg-primary/10 blur-3xl" />
        <div className="absolute -bottom-1/2 -left-1/2 w-[800px] h-[800px] rounded-full bg-purple-500/10 blur-3xl" />
      </div>

      {/* Grid pattern */}
      <div
        className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `linear-gradient(to right, currentColor 1px, transparent 1px),
            linear-gradient(to bottom, currentColor 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
        }}
      />

      <div className="relative z-10 w-full max-w-md px-4">
        <Card className="border-border/50 shadow-2xl bg-card/80 backdrop-blur-xl">
          <CardHeader className="space-y-4 text-center pb-8">
            <div className="mx-auto w-16 h-16 rounded-2xl gradient-primary flex items-center justify-center shadow-lg shadow-primary/25">
              <Send className="w-8 h-8 text-white" />
            </div>
            <div>
              <CardTitle className="text-2xl font-bold">Forwarder Pro</CardTitle>
              <CardDescription className="mt-2">
                {step === 'credentials'
                  ? '安全登录您的 Telegram 转发管理系统'
                  : '请输入双重验证码'}
              </CardDescription>
            </div>
          </CardHeader>

          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {step === 'credentials' ? (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="username">用户名</Label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="username"
                        placeholder="请输入用户名"
                        value={formData.username}
                        onChange={(e) =>
                          setFormData({ ...formData, username: e.target.value })
                        }
                        className="pl-10"
                        required
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="password">密码</Label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="password"
                        type={showPassword ? 'text' : 'password'}
                        placeholder="请输入密码"
                        value={formData.password}
                        onChange={(e) =>
                          setFormData({ ...formData, password: e.target.value })
                        }
                        className="pl-10 pr-10"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      >
                        {showPassword ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="remember"
                        checked={formData.remember}
                        onCheckedChange={(checked) =>
                          setFormData({ ...formData, remember: checked as boolean })
                        }
                      />
                      <Label htmlFor="remember" className="text-sm font-normal">
                        记住我
                      </Label>
                    </div>
                    <Button variant="link" className="text-sm h-auto p-0">
                      忘记密码？
                    </Button>
                  </div>
                </>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center justify-center p-4 bg-muted rounded-lg">
                    <Shield className="w-12 h-12 text-primary" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="2fa">双重验证码</Label>
                    <Input
                      id="2fa"
                      placeholder="000000"
                      maxLength={6}
                      value={formData.twoFactorCode}
                      onChange={(e) =>
                        setFormData({ ...formData, twoFactorCode: e.target.value })
                      }
                      className="text-center text-2xl tracking-[0.5em] font-mono"
                      required
                    />
                    <p className="text-xs text-muted-foreground text-center">
                      请输入验证器应用中的 6 位数字代码
                    </p>
                  </div>
                </div>
              )}

              <Button
                type="submit"
                className="w-full gradient-primary hover:opacity-90 transition-opacity"
                disabled={isLoading}
              >
                {isLoading ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    验证中...
                  </div>
                ) : step === 'credentials' ? (
                  '立即登录'
                ) : (
                  '验证并登录'
                )}
              </Button>

              {step === '2fa' && (
                <Button
                  type="button"
                  variant="ghost"
                  className="w-full"
                  onClick={() => setStep('credentials')}
                >
                  返回
                </Button>
              )}
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-sm text-muted-foreground mt-6">
          还没有账号？{' '}
          <Button variant="link" className="p-0 h-auto font-normal">
            联系管理员
          </Button>
        </p>
      </div>
    </div>
  );
}
