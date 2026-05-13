import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, Server, Monitor, ChevronDown, Search, Zap, BookOpen, Mail, Rocket, HelpCircle } from 'lucide-react';
import clsx from 'clsx';

const Accordion: React.FC<{ title: string; icon: React.ReactNode; children: React.ReactNode; defaultOpen?: boolean }> = ({ title, icon, children, defaultOpen = false }) => {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-200 rounded-2xl overflow-hidden transition-all hover:shadow-md">
      <button 
        onClick={() => setOpen(!open)} 
        className="w-full flex items-center justify-between px-6 py-5 bg-white hover:bg-slate-50 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <span className="text-indigo-500">{icon}</span>
          <span className="font-bold text-slate-800 text-sm md:text-base">{title}</span>
        </div>
        <ChevronDown className={clsx("w-5 h-5 text-slate-400 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="px-6 pb-6 bg-slate-50/50 animate-slide-in border-t border-slate-100">
          {children}
        </div>
      )}
    </div>
  );
};

export const FAQ: React.FC = () => {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');

  const sections = [
    {
      id: 'quickstart',
      title: t('faq_quickstart_title'),
      icon: <Rocket className="w-5 h-5" />,
      content: (
        <div className="pt-4 space-y-6">
          <div className="grid md:grid-cols-3 gap-4">
            {[
              { step: "01", title: t('faq_step1_title'), desc: t('faq_step1_desc'), color: "from-blue-500 to-blue-600" },
              { step: "02", title: t('faq_step2_title'), desc: t('faq_step2_desc'), color: "from-indigo-500 to-indigo-600" },
              { step: "03", title: t('faq_step3_title'), desc: t('faq_step3_desc'), color: "from-violet-500 to-violet-600" },
            ].map((s, i) => (
              <div key={i} className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm relative overflow-hidden">
                <div className={clsx("absolute top-0 right-0 w-16 h-16 bg-linear-to-br rounded-bl-4xl flex items-end justify-start pl-3 pb-2 text-white font-black text-lg", s.color)}>
                  {s.step}
                </div>
                <div className="mt-8">
                  <h4 className="font-black text-slate-800 text-sm mb-2">{s.title}</h4>
                  <p className="text-xs text-slate-500 leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      id: 'engines',
      title: t('faq_engine_compare_title'),
      icon: <Zap className="w-5 h-5" />,
      content: (
        <div className="pt-4 overflow-x-auto">
          <table className="w-full text-sm border-collapse min-w-[500px]">
            <thead>
              <tr className="bg-white">
                <th className="px-4 py-3 text-left text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-200">{t('faq_engine')}</th>
                <th className="px-4 py-3 text-center text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-200">{t('faq_speed')}</th>
                <th className="px-4 py-3 text-center text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-200">{t('faq_quality')}</th>
                <th className="px-4 py-3 text-center text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-200">{t('faq_cost')}</th>
                <th className="px-4 py-3 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-200">{t('faq_best_for')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {[
                { name: "Gemini 2.5 Flash", speed: "⚡⚡⚡", quality: "★★★★", cost: t('faq_cost_low'), best: t('faq_best_gemini') },
                { name: "Claude", speed: "⚡⚡", quality: "★★★★★", cost: t('faq_cost_high'), best: t('faq_best_claude') },
                { name: "Upstage Solar", speed: "⚡⚡⚡", quality: "★★★★", cost: t('faq_cost_mid'), best: t('faq_best_upstage') },
                { name: "Free (Google)", speed: "⚡⚡", quality: "★★★", cost: t('faq_cost_free'), best: t('faq_best_free') },
              ].map((eng, i) => (
                <tr key={i} className="bg-white hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 font-bold text-slate-800">{eng.name}</td>
                  <td className="px-4 py-3 text-center">{eng.speed}</td>
                  <td className="px-4 py-3 text-center text-amber-500">{eng.quality}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={clsx(
                      "text-[10px] font-black px-2.5 py-1 rounded-full",
                      eng.cost === t('faq_cost_free') ? "bg-green-50 text-green-600 border border-green-100" :
                      eng.cost === t('faq_cost_high') ? "bg-red-50 text-red-600 border border-red-100" :
                      "bg-amber-50 text-amber-600 border border-amber-100"
                    )}>{eng.cost}</span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">{eng.best}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ),
    },
    {
      id: 'glossary',
      title: t('faq_g_title'),
      icon: <BookOpen className="w-5 h-5" />,
      content: (
        <div className="pt-4 space-y-4">
          <p className="text-slate-600 leading-relaxed text-sm">{t('faq_g_p1')}</p>
          <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm">
            <p className="font-black text-blue-600 mb-2 text-sm">{t('faq_g_q')}</p>
            <p className="text-slate-500 text-sm italic leading-relaxed">{t('faq_g_a')}</p>
          </div>
        </div>
      ),
    },
    {
      id: 'architecture',
      title: t('faq_arch_title'),
      icon: <Server className="w-5 h-5" />,
      content: (
        <div className="pt-4 grid md:grid-cols-2 gap-4">
          <div className="bg-blue-50/50 rounded-2xl p-6 border border-blue-100">
            <h4 className="font-black text-blue-900 mb-3 flex items-center gap-2 text-sm">
              <Monitor className="w-5 h-5" /> {t('faq_client_title')}
            </h4>
            <ul className="space-y-2 text-xs text-blue-800/80 font-bold">
              <li className="flex gap-2"><span className="text-green-500">✓</span> {t('faq_client_pros1')}</li>
              <li className="flex gap-2"><span className="text-green-500">✓</span> {t('faq_client_pros2')}</li>
              <li className="flex gap-2"><span className="text-red-500">✗</span> {t('faq_client_cons1')}</li>
              <li className="flex gap-2"><span className="text-red-500">✗</span> {t('faq_client_cons2')}</li>
            </ul>
          </div>
          <div className="bg-indigo-50/50 rounded-2xl p-6 border border-indigo-100">
            <h4 className="font-black text-indigo-900 mb-3 flex items-center gap-2 text-sm">
              <Server className="w-5 h-5" /> {t('faq_server_title')}
            </h4>
            <ul className="space-y-2 text-xs text-indigo-800/80 font-bold">
              <li className="flex gap-2"><span className="text-green-500">✓</span> {t('faq_server_pros1')}</li>
              <li className="flex gap-2"><span className="text-green-500">✓</span> {t('faq_server_pros2')}</li>
              <li className="flex gap-2"><span className="text-amber-500">△</span> {t('faq_server_cons1')}</li>
            </ul>
          </div>
        </div>
      ),
    },
    {
      id: 'warnings',
      title: t('faq_warn_title'),
      icon: <AlertTriangle className="w-5 h-5" />,
      content: (
        <div className="pt-4">
          <div className="bg-amber-50 rounded-2xl p-5 text-amber-900 border border-amber-200">
            <ul className="space-y-3 text-sm font-bold">
              <li className="flex gap-3"><div className="w-2 h-2 bg-amber-400 rounded-full mt-1.5 shrink-0"></div>{t('faq_warn_l1')}</li>
              <li className="flex gap-3"><div className="w-2 h-2 bg-amber-400 rounded-full mt-1.5 shrink-0"></div>{t('faq_warn_l2')}</li>
              <li className="flex gap-3"><div className="w-2 h-2 bg-amber-400 rounded-full mt-1.5 shrink-0"></div>{t('faq_warn_l3')}</li>
            </ul>
          </div>
        </div>
      ),
    },
    {
      id: 'contact',
      title: t('contact_title'),
      icon: <Mail className="w-5 h-5" />,
      content: (
        <div className="pt-4">
          <div className="bg-blue-50 rounded-2xl p-5 text-center border border-blue-200">
            <p className="text-slate-600 mb-3 text-sm">{t('contact_desc')}</p>
            <a href="mailto:js222@bubblecon.io" className="inline-flex items-center gap-2 text-blue-600 font-black text-sm hover:underline">
              <Mail className="w-4 h-4" /> js222@bubblecon.io
            </a>
          </div>
        </div>
      ),
    },
  ];

  const filteredSections = search.trim()
    ? sections.filter(s => s.title.toLowerCase().includes(search.toLowerCase()))
    : sections;

  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-16 animate-fade-in">
      <div className="bg-white rounded-[2.5rem] shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden">
        {/* Header */}
        <div className="bg-linear-to-br from-blue-600 to-indigo-600 px-10 py-12 text-white relative overflow-hidden">
          <div className="relative z-10">
            <h2 className="text-4xl font-black mb-3 tracking-tight">{t('tab_faq')}</h2>
            <p className="text-blue-100 text-lg font-medium max-w-xl">{t('faq_desc')}</p>
          </div>
          <div className="absolute top-0 right-0 -translate-y-1/2 translate-x-1/4 w-96 h-96 bg-white/10 rounded-full blur-3xl"></div>
        </div>

        {/* Search */}
        <div className="px-10 py-6 border-b border-slate-100 bg-slate-50/30">
          <div className="relative max-w-lg">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
            <input 
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('faq_search_placeholder')}
              className="w-full bg-white border border-slate-200 rounded-2xl pl-12 pr-4 py-3 text-sm font-medium focus:ring-2 focus:ring-blue-500 outline-none transition-all"
            />
          </div>
        </div>

        {/* FAQ Sections */}
        <div className="p-10 space-y-4">
          {filteredSections.length === 0 ? (
            <div className="text-center py-16">
              <HelpCircle className="w-12 h-12 text-slate-200 mx-auto mb-4" />
              <p className="text-slate-400 font-bold">{t('faq_no_results')}</p>
            </div>
          ) : (
            filteredSections.map((section, i) => (
              <Accordion key={section.id} title={section.title} icon={section.icon} defaultOpen={i === 0 && !search}>
                {section.content}
              </Accordion>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
