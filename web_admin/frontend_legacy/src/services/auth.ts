import api from '@/lib/api';

export const authService = {
  login: (data: any) => 
    api.post('/auth/login', data),
    
  login2fa: (data: { pre_auth_token: string, token: string }) => 
    api.post('/auth/login/2fa', data),
    
  logout: () => 
    api.post('/auth/logout'),
};
