"use client";

import React, { useState, useEffect } from "react";

const API_BASE = "http://localhost:8000";

interface Candidate {
  id: string;
  name: string;
  org: string;
  year: string;
  advt_number: string;
  post?: string;
}

interface ReportVersion {
  id: string;
  version: string;
  changed_sections: string[];
  created_at: string;
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [education, setEducation] = useState("");
  const [age, setAge] = useState("");
  const [category, setCategory] = useState("General");
  const [showProfile, setShowProfile] = useState(false);

  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<string>("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);

  const [report, setReport] = useState<any>(null);
  const [reportVersion, setReportVersion] = useState<string>("1.0");
  const [availableVersions, setAvailableVersions] = useState<ReportVersion[]>([]);
  const [activeTab, setActiveTab] = useState<string>("overview");

  const [changeRequestText, setChangeRequestText] = useState("");
  const [isSubmittingChange, setIsSubmittingChange] = useState(false);
  const [sources, setSources] = useState<any>({ official_sources: [], secondary_sources: [] });
  const [conflicts, setConflicts] = useState<any[]>([]);

  // Job Polling
  useEffect(() => {
    if (!jobId || jobStatus === "completed" || jobStatus === "failed") return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/research/${jobId}/status`);
        if (!res.ok) return;
        const data = await res.json();
        setJobStatus(data.status);
        setCurrentStep(data.current_step);

        if (data.status === "ambiguous" && data.candidates) {
          setCandidates(data.candidates);
        }

        if (data.status === "completed") {
          fetchReport(jobId);
          fetchVersions(jobId);
          fetchSources(jobId);
          fetchConflicts(jobId);
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId, jobStatus]);

  const startResearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setJobId(null);
    setJobStatus("pending");
    setReport(null);
    setCandidates([]);

    try {
      const res = await fetch(`${API_BASE}/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_query: query,
          user_profile: {
            education: education || undefined,
            age: age ? parseInt(age) : undefined,
            category: category || "General",
          },
        }),
      });
      const data = await res.json();
      setJobId(data.job_id);
    } catch (err) {
      alert("Failed to connect to backend server at " + API_BASE);
      setJobStatus(null);
    }
  };

  const resolveRecruitment = async (candidateId: string) => {
    if (!jobId) return;
    try {
      await fetch(`${API_BASE}/research/${jobId}/resolve-recruitment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_candidate_id: candidateId }),
      });
      setJobStatus("running");
      setCandidates([]);
    } catch (err) {
      alert("Failed to resolve recruitment candidate");
    }
  };

  const fetchReport = async (jId: string, ver?: string) => {
    try {
      const url = ver ? `${API_BASE}/research/${jId}/report?version=${ver}` : `${API_BASE}/research/${jId}/report`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setReport(data.sections);
        setReportVersion(data.version);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchVersions = async (jId: string) => {
    try {
      const res = await fetch(`${API_BASE}/research/${jId}/report/versions`);
      if (res.ok) {
        const data = await res.json();
        setAvailableVersions(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchSources = async (jId: string) => {
    try {
      const res = await fetch(`${API_BASE}/research/${jId}/sources`);
      if (res.ok) {
        const data = await res.json();
        setSources(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchConflicts = async (jId: string) => {
    try {
      const res = await fetch(`${API_BASE}/research/${jId}/conflicts`);
      if (res.ok) {
        const data = await res.json();
        setConflicts(data.conflicts || []);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const submitChangeRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobId || !changeRequestText.trim()) return;

    setIsSubmittingChange(true);
    try {
      await fetch(`${API_BASE}/research/${jobId}/request-change`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_text: changeRequestText }),
      });
      setChangeRequestText("");
      alert("Change request submitted! Re-research in progress...");
      setTimeout(() => {
        if (jobId) {
          fetchReport(jobId);
          fetchVersions(jobId);
        }
      }, 4000);
    } catch (err) {
      alert("Error submitting request change");
    } finally {
      setIsSubmittingChange(false);
    }
  };

  const downloadPDF = () => {
    if (!jobId) return;
    window.open(`${API_BASE}/research/${jobId}/pdf?version=${reportVersion}`, "_blank");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Header Bar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-40 px-6 py-4 flex justify-between items-center">
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-emerald-400 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/20">
            GL
          </div>
          <div>
            <h1 className="font-bold text-lg leading-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
              GovLens AI
            </h1>
            <p className="text-xs text-slate-400">Evidence-driven intelligence for government recruitment.</p>
          </div>
        </div>
        {jobId && report && (
          <button
            onClick={downloadPDF}
            className="bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm px-4 py-2 rounded-lg transition shadow-md shadow-emerald-900/30 flex items-center space-x-2"
          >
            <span>Download Cited PDF</span>
          </button>
        )}
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Search & Profile Section */}
        <section className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 shadow-xl space-y-4">
          <form onSubmit={startResearch} className="space-y-4">
            <div className="flex flex-col md:flex-row gap-3">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter Government Exam e.g. 'BPSC TRE 4.0 Computer Science', 'SSC CGL 2026', 'UPSC CDS 2026'"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 placeholder-slate-500"
              />
              <button
                type="button"
                onClick={() => setShowProfile(!showProfile)}
                className="bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-3 rounded-xl text-sm font-medium border border-slate-700 transition"
              >
                {showProfile ? "Hide Profile" : "Add My Profile"}
              </button>
              <button
                type="submit"
                className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-xl text-sm font-semibold transition shadow-lg shadow-indigo-600/30"
              >
                Start AI Research
              </button>
            </div>

            {showProfile && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-slate-800">
                <div>
                  <label className="text-xs text-slate-400 font-medium">My Degree / Qualification</label>
                  <input
                    type="text"
                    value={education}
                    onChange={(e) => setEducation(e.target.value)}
                    placeholder="e.g. B.Tech Computer Science, MCA, B.Sc"
                    className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 font-medium">My Age (Years)</label>
                  <input
                    type="number"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                    placeholder="e.g. 25"
                    className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 font-medium">Category</label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200"
                  >
                    <option value="General">General / UR</option>
                    <option value="OBC">OBC</option>
                    <option value="EWS">EWS</option>
                    <option value="SC">SC</option>
                    <option value="ST">ST</option>
                  </select>
                </div>
              </div>
            )}
          </form>
        </section>

        {/* Live Progress Bar */}
        {jobStatus && jobStatus !== "completed" && jobStatus !== "ambiguous" && (
          <div className="bg-slate-900 border border-indigo-500/30 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm font-semibold text-indigo-400 animate-pulse">
                Autonomous Multi-Agent Pipeline Executing... ({currentStep})
              </span>
              <span className="text-xs text-slate-400 uppercase tracking-wider">{jobStatus}</span>
            </div>
            <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
              <div className="bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 h-2 rounded-full animate-pulse w-3/4"></div>
            </div>
          </div>
        )}

        {/* Ambiguity Resolution Modal */}
        {jobStatus === "ambiguous" && candidates.length > 0 && (
          <div className="bg-amber-950/40 border border-amber-500/50 rounded-2xl p-6 space-y-4 shadow-2xl">
            <h3 className="font-bold text-amber-400 text-lg">Ambiguous Recruitment Query Detected</h3>
            <p className="text-sm text-slate-300">
              Multiple distinct advertisement cycles or years were found matching your query. Select the exact recruitment to proceed:
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {candidates.map((cand, idx) => (
                <div
                  key={cand.id || cand.advt_number || idx}
                  className="bg-slate-900 border border-slate-800 rounded-xl p-4 hover:border-indigo-500 cursor-pointer transition space-y-2"
                  onClick={() => resolveRecruitment(cand.id || cand.advt_number || cand.name || `cand_${idx + 1}`)}
                >
                  <h4 className="font-bold text-indigo-300 text-base">{cand.name}</h4>
                  <p className="text-xs text-slate-400">Org: {cand.org} | Advt: {cand.advt_number} | Year: {cand.year}</p>
                  <button className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-md font-medium transition">
                    Lock In Selection
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Report Display */}
        {report && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
            {/* Main Report Section */}
            <div className="lg:col-span-3 space-y-6">
              {/* Report Header & Version Selector */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                  <h2 className="text-xl font-bold text-white">Verified Research Report</h2>
                  <p className="text-xs text-slate-400">Strictly synthesized from official notifications & corrigenda</p>
                </div>
                <div className="flex items-center space-x-3">
                  <span className="text-xs text-slate-400">Report Version:</span>
                  <select
                    value={reportVersion}
                    onChange={(e) => {
                      if (jobId) fetchReport(jobId, e.target.value);
                    }}
                    className="bg-slate-950 border border-slate-800 rounded-lg text-xs text-indigo-300 font-semibold px-3 py-1.5"
                  >
                    {availableVersions.map((v) => (
                      <option key={v.id} value={v.version}>
                        v{v.version} ({new Date(v.created_at).toLocaleTimeString()})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Navigation Tabs */}
              <div className="flex overflow-x-auto space-x-2 border-b border-slate-800 pb-2">
                {[
                  { id: "overview", label: "Overview" },
                  { id: "dates", label: "Important Dates" },
                  { id: "eligibility", label: "Eligibility" },
                  { id: "personalized", label: "Personalized Eligibility" },
                  { id: "vacancies", label: "Vacancies" },
                  { id: "fees_salary", label: "Salary & Fees" },
                  { id: "selection", label: "Selection Process" },
                  { id: "syllabus", label: "Pattern & Syllabus" },
                  { id: "procedure", label: "Application Procedure" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`px-4 py-2 text-xs font-semibold rounded-lg whitespace-nowrap transition ${
                      activeTab === tab.id ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20" : "text-slate-400 hover:text-white hover:bg-slate-900"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab Contents */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 min-h-[350px]">
                {activeTab === "overview" && (
                  <div className="space-y-4">
                    <h3 className="text-lg font-bold text-indigo-400">1. Exam Overview</h3>
                    <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">{report.exam_overview}</p>
                  </div>
                )}

                {activeTab === "dates" && (
                  <div className="space-y-4">
                    <h3 className="text-lg font-bold text-indigo-400">2. Important Dates</h3>
                    <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-sm text-slate-300 whitespace-pre-line">
                      {report.important_dates}
                    </div>
                  </div>
                )}

                {activeTab === "eligibility" && (
                  <div className="space-y-4">
                    <h3 className="text-lg font-bold text-indigo-400">3. Eligibility Criteria</h3>
                    <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-sm text-slate-300 whitespace-pre-line">
                      {report.eligibility}
                    </div>
                  </div>
                )}

                {activeTab === "personalized" && (
                  <div className="space-y-4">
                    <h3 className="text-lg font-bold text-indigo-400">4. Personalized Eligibility Evaluation</h3>
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400">
                          <th className="py-2">Requirement</th>
                          <th className="py-2">Official Requirement</th>
                          <th className="py-2">User Profile</th>
                          <th className="py-2">Evaluation Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/50">
                        {report.personalized_eligibility &&
                          report.personalized_eligibility.map((item: any, idx: number) => (
                            <tr key={idx} className="hover:bg-slate-950/50">
                              <td className="py-3 font-semibold text-slate-200">{item.requirement}</td>
                              <td className="py-3 text-slate-400">{item.official}</td>
                              <td className="py-3 text-slate-400">{item.user_profile}</td>
                              <td className="py-3">
                                <span
                                  className={`px-2.5 py-1 rounded-full font-bold text-[10px] uppercase tracking-wider ${
                                    item.status === "Eligible"
                                      ? "bg-emerald-950 text-emerald-400 border border-emerald-500/30"
                                      : item.status === "Not Eligible"
                                      ? "bg-rose-950 text-rose-400 border border-rose-500/30"
                                      : "bg-amber-950 text-amber-400 border border-amber-500/30"
                                  }`}
                                >
                                  {item.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {activeTab === "vacancies" && (
                  <div className="space-y-4">
                    <h3 className="text-lg font-bold text-indigo-400">5. Vacancy Details</h3>
                    <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-sm text-slate-300 whitespace-pre-line">
                      {report.vacancies}
                    </div>
                  </div>
                )}

                {activeTab === "fees_salary" && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-lg font-bold text-indigo-400">6. Salary & Pay Scale</h3>
                      <p className="text-sm text-slate-300 mt-2">{report.salary}</p>
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-indigo-400">7. Application Fees</h3>
                      <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-sm text-slate-300 whitespace-pre-line mt-2">
                        {report.application_fees}
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === "selection" && (
                  <div className="space-y-4">
                    <h3 className="text-lg font-bold text-indigo-400">9. Selection Process</h3>
                    <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">{report.selection_process}</p>
                  </div>
                )}

                {activeTab === "syllabus" && (
                  <div className="space-y-4">
                    <h3 className="text-lg font-bold text-indigo-400">10. Exam Pattern & Syllabus</h3>
                    <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">{report.exam_pattern_syllabus}</p>
                  </div>
                )}

                {activeTab === "procedure" && (
                  <div className="space-y-4">
                    <h3 className="text-lg font-bold text-indigo-400">11. Application Procedure</h3>
                    <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-sm text-slate-300 whitespace-pre-line">
                      {report.application_procedure}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Sidebar: HITL Ask AI Drawer & Sources / Conflicts Inspector */}
            <div className="space-y-6">
              {/* HITL Request Box */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-xl">
                <h3 className="font-bold text-slate-200 text-base">Request Targeted Re-Research</h3>
                <p className="text-xs text-slate-400">
                  Ask AI to clarify or re-verify specific sections without restarting the full workflow.
                </p>
                <form onSubmit={submitChangeRequest} className="space-y-3">
                  <textarea
                    value={changeRequestText}
                    onChange={(e) => setChangeRequestText(e.target.value)}
                    placeholder="e.g. 'Re-verify eligibility for MCA degree' or 'Check revised exam dates'"
                    rows={3}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                  <button
                    type="submit"
                    disabled={isSubmittingChange}
                    className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs py-2.5 rounded-xl transition shadow-md shadow-indigo-600/20"
                  >
                    {isSubmittingChange ? "Submitting..." : "Submit Change Request"}
                  </button>
                </form>
              </div>

              {/* Sources Inspector */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3 shadow-xl">
                <h3 className="font-bold text-slate-200 text-sm">Official Sources Used ({sources.official_sources.length})</h3>
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {sources.official_sources.map((s: any, idx: number) => (
                    <a
                      key={idx}
                      href={s.url}
                      target="_blank"
                      rel="noreferrer"
                      className="block bg-slate-950 p-2.5 rounded-lg border border-slate-800/80 hover:border-emerald-500/50 transition"
                    >
                      <div className="text-xs font-semibold text-emerald-400 truncate">{s.title || s.url}</div>
                      <div className="text-[10px] text-slate-500 uppercase tracking-wider mt-0.5">{s.source_type}</div>
                    </a>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
