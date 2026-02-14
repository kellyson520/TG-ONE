import api from '@/lib/api';

export const statsService = {
    getOverview: (): Promise<{ success: boolean; data: any }> =>
        api.get('/stats/overview'),

    getSystemResources: (): Promise<{ success: boolean; data: any }> =>
        api.get('/stats/system_resources'),

    getSeries: (days: number = 7): Promise<{ success: boolean; data: any }> =>
        api.get(`/stats/series?days=${days}`),
};
