import Link from "next/link";
import { ArrowRight, BadgeCheck, Globe2, Radar, ShieldCheck, Sparkles } from "lucide-react";

const pillars = [
  {
    title: "Legitimacy",
    description: "Checks company identity, hiring links, contact details, and suspicious payment requests.",
    icon: ShieldCheck
  },
  {
    title: "Remote Authenticity",
    description: "Checks whether the role appears genuinely remote and office-free.",
    icon: Radar
  },
  {
    title: "Global Eligibility",
    description: "Checks country, timezone, and work authorization fit for the applicant.",
    icon: Globe2
  },
  {
    title: "Job Quality",
    description: "Checks role clarity, pay, skills, benefits, and hiring process details.",
    icon: Sparkles
  }
];

export default function LandingPage() {
  return (
    <main>
      <section className="relative min-h-[calc(100vh-68px)] overflow-hidden border-b border-line">
        <div className="absolute inset-0 grid-overlay opacity-60" aria-hidden="true" />
        <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(8,17,31,0.34),rgba(11,78,83,0.48),rgba(74,39,82,0.34))]" aria-hidden="true" />
        <div className="relative mx-auto flex min-h-[calc(100vh-68px)] max-w-7xl flex-col justify-center px-4 py-16 sm:px-6 lg:px-8">
          <div className="max-w-4xl">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-mint/30 bg-mint/[0.10] px-3 py-1.5 text-sm font-semibold text-mint">
              <BadgeCheck size={16} aria-hidden="true" />
              AI-powered remote job verification
            </div>
            <h1 className="text-5xl font-black leading-[1.02] text-white sm:text-6xl lg:text-7xl">RemoteTrust AI</h1>
            <p className="mt-6 max-w-3xl text-lg leading-8 text-slate-200 sm:text-xl">
              Find remote jobs that are real, high-quality, and actually open to global applicants.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link href="/analyze" className="btn-primary">
                Analyze a Job <ArrowRight size={18} aria-hidden="true" />
              </Link>
              <Link href="/opportunities" className="btn-secondary">
                Curated Feed
              </Link>
            </div>
          </div>

          <div className="mt-16 grid max-w-4xl gap-3 sm:grid-cols-4">
            {[
              ["40%", "Company trust"],
              ["25%", "Remote clarity"],
              ["20%", "Applicant fit"],
              ["15%", "Job quality"]
            ].map(([value, label]) => (
              <div key={label} className="rounded-lg border border-line bg-ink/[0.48] p-4 backdrop-blur">
                <div className="text-2xl font-black text-white">{value}</div>
                <div className="mt-1 text-sm text-slate-400">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="pillars" className="px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="max-w-3xl">
            <p className="label">Checks</p>
            <h2 className="mt-3 text-3xl font-black text-white sm:text-4xl">Four checks before a global applicant spends hours applying.</h2>
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {pillars.map((pillar) => {
              const Icon = pillar.icon;
              return (
                <article key={pillar.title} className="surface rounded-lg p-6">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-cyan/30 bg-cyan/[0.10] text-cyan">
                    <Icon size={22} aria-hidden="true" />
                  </div>
                  <h3 className="mt-5 text-lg font-bold text-white">{pillar.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-slate-400">{pillar.description}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>
    </main>
  );
}
