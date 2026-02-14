import api from '@/lib/api';

export const rulesService = {
    getRules: (page: number = 1, size: number = 50) =>
        api.get(`/rules?page=${page}&size=${size}`),

    createRule: (data: any) =>
        api.post('/rules', data),

    getRuleDetail: (id: number) =>
        api.get(`/rules/${id}`),

    updateRule: (id: number, data: any) =>
        api.put(`/rules/${id}`, data),

    deleteRule: (id: number) =>
        api.delete(`/rules/${id}`),

    toggleRule: (id: number) =>
        api.post(`/rules/${id}/toggle`),
};
