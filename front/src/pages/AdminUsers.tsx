import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { Users, Activity, DollarSign, ChevronDown, ChevronUp, FileText, Download, CheckCircle, AlertCircle, Loader2, Ban, Clock } from 'lucide-react';
import clsx from 'clsx';
import { getApiUrl } from '../api';

interface UserStat {
  username: string;
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  total_cost: number;
  total_size: number;
  last_activity: string;
}

interface Job {
  job_id: string;
  timestamp: string;
  filename: string;
  provider: string;
  target_lang: string;
  status: string;
  output_path: string;
  file_size?: number;
  cost?: number;
}

export const AdminUsers: React.FC = () => {
  const { token } = useAuth();
  const { t, i18n } = useTranslation();
  const [stats, setStats] = useState<UserStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedUser, setExpandedUser] = useState<string | null>(null);
  const [userJobs, setUserJobs] = useState<Job[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);

  useEffect(() => {
    if (token) {
      axios.get(getApiUrl('/admin/users'), {
        headers: { Authorization: `Bearer ${token}` }
      }).then(res => setStats(res.data))
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [token]);

  const toggleUser = async (username: string) => {
    if (expandedUser === username) {
      setExpandedUser(null);
      return;
    }
    setExpandedUser(username);
    setJobsLoading(true);
    try {
      const res = await axios.get(getApiUrl(`/admin/user-jobs/${username}`), {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUserJobs(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setJobsLoading(false);
    }
  };

  const totalJobs = stats.reduce((s, u) => s + u.total_jobs, 0);
  const totalCost = stats.reduce((s, u) => s + u.total_cost, 0);
  const totalCompleted = stats.reduce((s, u) => s + u.completed_jobs, 0);

  const getStatusBadge = (status: string) => {
    const map: Record<string, { icon: React.ReactNode, cls: string, label: string }> = {
      completed: { icon: <CheckCircle className="w-3 h-3" />, cls: "text-green-600 bg-green-50 border-green-100", label: t('status_completed') },
      processing: { icon: <Loader2 className="w-3 h-3 animate-spin" />, cls: "text-blue-600 bg-blue-50 border-blue-100", label: t('status_processing') },
      failed: { icon: <AlertCircle className="w-3 h-3" />, cls: "text-red-600 bg-red-50 border-red-100", label: t('status_failed') },
      cancelled: { icon: <Ban className="w-3 h-3" />, cls: "text-amber-600 bg-amber-50 border-amber-100", label: t('status_cancelled') },
      timeout: { icon: <Clock className="w-3 h-3" />, cls: "text-slate-600 bg-slate-50 border-slate-200", label: t('status_timeout') },
    };
    const s = map[status] || { icon: null, cls: "text-slate-400", label: status };
    return (
      <span className={clsx("inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-black border shadow-sm whitespace-nowrap", s.cls)}>
        {s.icon} {s.label}
      </span>
    );
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-16 animate-fade-in px-4">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {[
          { label: t('admin_total_users'), value: stats.length, icon: <Users className="w-6 h-6" />, color: "from-blue-500 to-blue-600", shadow: "shadow-blue-200" },
          { label: t('admin_total_jobs'), value: totalJobs, icon: <FileText className="w-6 h-6" />, color: "from-indigo-500 to-indigo-600", shadow: "shadow-indigo-200" },
          { label: t('admin_completed'), value: totalCompleted, icon: <Activity className="w-6 h-6" />, color: "from-emerald-500 to-emerald-600", shadow: "shadow-emerald-200" },
          { label: t('admin_total_cost'), value: `$${totalCost.toFixed(4)}`, icon: <DollarSign className="w-6 h-6" />, color: "from-amber-500 to-amber-600", shadow: "shadow-amber-200" },
        ].map((card, i) => (
          <div key={i} className={clsx("bg-white rounded-2xl p-6 border border-slate-100 shadow-lg", card.shadow)}>
            <div className="flex items-center justify-between mb-4">
              <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{card.label}</span>
              <div className={clsx("bg-linear-to-br text-white p-2 rounded-xl", card.color)}>
                {card.icon}
              </div>
            </div>
            <p className="text-3xl font-black text-slate-800 tabular-nums">{card.value}</p>
          </div>
        ))}
      </div>

      {/* User List */}
      <div className="bg-white rounded-[2.5rem] shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden">
        <div className="p-8 border-b border-slate-50 bg-slate-50/30">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 bg-linear-to-br from-violet-500 to-purple-600 rounded-2xl flex items-center justify-center text-white shadow-lg shadow-violet-200">
              <Users className="w-7 h-7" />
            </div>
            <div>
              <h2 className="text-3xl font-black text-slate-800 tracking-tight">{t('admin_user_management')}</h2>
              <p className="text-slate-400 font-black uppercase tracking-widest text-[10px] mt-1">User Analytics</p>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="py-32 flex flex-col justify-center items-center gap-4">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-indigo-100 rounded-full"></div>
              <div className="w-16 h-16 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin absolute top-0"></div>
            </div>
          </div>
        ) : stats.length === 0 ? (
          <div className="text-center py-32 space-y-4">
            <Users className="w-16 h-16 text-slate-200 mx-auto" />
            <p className="text-slate-400 font-bold text-lg">{t('admin_no_users')}</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-50">
            {stats.map((user) => (
              <div key={user.username}>
                <button 
                  onClick={() => toggleUser(user.username)}
                  className="w-full px-8 py-6 flex items-center justify-between hover:bg-slate-50/80 transition-all text-left"
                >
                  <div className="flex items-center gap-5">
                    <div className="w-12 h-12 bg-linear-to-br from-slate-100 to-slate-200 rounded-2xl flex items-center justify-center text-slate-500 font-black text-lg uppercase">
                      {user.username.charAt(0)}
                    </div>
                    <div>
                      <p className="font-bold text-slate-800 text-sm">{user.username}</p>
                      <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mt-0.5">
                        {t('admin_last_active')}: {user.last_activity ? new Date(user.last_activity).toLocaleDateString(i18n.language === 'ko' ? 'ko-KR' : 'en-US') : '-'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="text-center hidden md:block">
                      <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest">{t('admin_total_jobs')}</p>
                      <p className="text-lg font-black text-slate-700 tabular-nums">{user.total_jobs}</p>
                    </div>
                    <div className="text-center hidden md:block">
                      <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest">{t('admin_completed')}</p>
                      <p className="text-lg font-black text-emerald-600 tabular-nums">{user.completed_jobs}</p>
                    </div>
                    <div className="text-center hidden md:block">
                      <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest">{t('admin_total_cost')}</p>
                      <p className="text-lg font-black text-indigo-600 tabular-nums">${user.total_cost.toFixed(4)}</p>
                    </div>
                    {expandedUser === user.username ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
                  </div>
                </button>

                {expandedUser === user.username && (
                  <div className="px-8 pb-6 animate-slide-in">
                    {jobsLoading ? (
                      <div className="py-8 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-indigo-400" /></div>
                    ) : (
                      <div className="overflow-x-auto rounded-2xl border border-slate-200">
                        <table className="w-full text-left border-collapse min-w-[700px]">
                          <thead>
                            <tr className="bg-slate-50">
                              <th className="px-4 py-3 text-[10px] font-black text-slate-400 uppercase tracking-widest">{t('history_date')}</th>
                              <th className="px-4 py-3 text-[10px] font-black text-slate-400 uppercase tracking-widest">{t('history_filename')}</th>
                              <th className="px-4 py-3 text-[10px] font-black text-slate-400 uppercase tracking-widest text-center">{t('history_engine')}</th>
                              <th className="px-4 py-3 text-[10px] font-black text-slate-400 uppercase tracking-widest text-center">{t('history_status')}</th>
                              <th className="px-4 py-3 text-[10px] font-black text-slate-400 uppercase tracking-widest text-right">{t('history_cost')}</th>
                              <th className="px-4 py-3 text-[10px] font-black text-slate-400 uppercase tracking-widest text-right">{t('history_download')}</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-50">
                            {userJobs.map(job => (
                              <tr key={job.job_id} className="hover:bg-slate-50/50 transition-colors">
                                <td className="px-4 py-3 text-[11px] font-bold text-slate-400 tabular-nums whitespace-nowrap">
                                  {new Date(job.timestamp).toLocaleString(i18n.language === 'ko' ? 'ko-KR' : 'en-US')}
                                </td>
                                <td className="px-4 py-3 text-sm font-bold text-slate-700 truncate max-w-[200px]" title={job.filename}>{job.filename}</td>
                                <td className="px-4 py-3 text-center">
                                  <span className="text-[10px] font-black text-slate-500 bg-white border border-slate-200 px-2 py-1 rounded-lg uppercase">{job.provider}</span>
                                </td>
                                <td className="px-4 py-3 text-center">{getStatusBadge(job.status)}</td>
                                <td className="px-4 py-3 text-right text-xs font-black text-indigo-600 tabular-nums">${job.cost?.toFixed(4) || "0.0000"}</td>
                                <td className="px-4 py-3 text-right">
                                  {job.status === 'completed' && job.output_path ? (
                                    <a href={getApiUrl(`/download/${job.job_id}`)} target="_blank" rel="noopener noreferrer"
                                       className="inline-flex items-center gap-1.5 text-blue-600 hover:text-white hover:bg-blue-600 font-black text-[10px] uppercase bg-blue-50 px-3 py-1.5 rounded-lg border border-blue-100 transition-all">
                                      <Download className="w-3 h-3" /> {t('history_download')}
                                    </a>
                                  ) : <span className="text-slate-300">-</span>}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
