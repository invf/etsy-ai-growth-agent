import { useLocale, useTranslations } from 'next-intl'
import { ArrowRight, TrendingUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SeoAnalysis } from '@/types'
import CopyableDescription from '@/components/seo/CopyableDescription'
import CopyableAltText from '@/components/seo/CopyableAltText'

const PRIORITY_STYLES: Record<SeoAnalysis['priority'], string> = {
  critical: 'bg-red-100 text-red-700',
  high: 'bg-amber-100 text-amber-700',
  medium: 'bg-blue-100 text-blue-700',
  low: 'bg-zinc-100 text-zinc-600',
}

function Score({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-3 text-center">
      <p className="text-xs uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums">{value ?? '—'}</p>
    </div>
  )
}

function Tags({ tags, tone = 'default' }: { tags: string[]; tone?: 'default' | 'good' | 'bad' }) {
  const styles = {
    default: 'bg-zinc-100 text-zinc-700',
    good: 'bg-green-100 text-green-700',
    bad: 'bg-red-50 text-red-600 line-through decoration-red-300',
  }
  return (
    <span className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <span key={tag} className={cn('rounded-full px-2 py-0.5 text-xs', styles[tone])}>
          {tag}
        </span>
      ))}
    </span>
  )
}

export default function SeoAnalysisPanel({ analysis }: { analysis: SeoAnalysis }) {
  const t = useTranslations('listingDetail.analysis')
  const locale = useLocale()
  const title = analysis.title_analysis
  const tags = analysis.tags_analysis
  const description = analysis.description_analysis
  const images = analysis.image_alt_analysis

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            'rounded-full px-3 py-1 text-xs font-semibold uppercase',
            PRIORITY_STYLES[analysis.priority]
          )}
        >
          {t(`priority.${analysis.priority}`)}
        </span>
        {analysis.estimated_traffic_lift_pct !== null && (
          <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700">
            <TrendingUp className="h-3 w-3" aria-hidden />
            {t('trafficLift', { pct: analysis.estimated_traffic_lift_pct })}
          </span>
        )}
        <span className="text-xs text-zinc-400">
          {t('analyzedAt', {
            date: new Date(analysis.created_at).toLocaleString(locale),
          })}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Score label={t('scores.overall')} value={analysis.overall_score} />
        <Score label={t('scores.title')} value={analysis.title_score} />
        <Score label={t('scores.tags')} value={analysis.tags_score} />
        <Score label={t('scores.description')} value={analysis.description_score} />
      </div>

      <section className="rounded-xl border border-zinc-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-zinc-900">{t('title.heading')}</h3>
        <div className="mt-2 grid grid-cols-1 items-start gap-2 text-sm md:grid-cols-[1fr_auto_1fr]">
          <p className="text-zinc-500 line-through decoration-zinc-300">
            {title.current_title ?? '—'}
          </p>
          <ArrowRight className="hidden h-4 w-4 self-center text-zinc-400 md:block" aria-hidden />
          <p className="font-medium text-zinc-900">{title.optimized_title ?? '—'}</p>
        </div>
        {title.change_rationale && (
          <p className="mt-2 text-xs text-zinc-500">{title.change_rationale}</p>
        )}
        {title.issues.length > 0 && (
          <ul className="mt-2 list-inside list-disc text-xs text-zinc-500">
            {title.issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-xl border border-zinc-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-zinc-900">{t('tags.heading')}</h3>
        <div className="mt-3 space-y-3 text-sm">
          <div>
            <p className="mb-1 text-xs text-zinc-500">{t('tags.optimized')}</p>
            <Tags tags={tags.optimized_tags} tone="good" />
          </div>
          {tags.weak_tags.length > 0 && (
            <div>
              <p className="mb-1 text-xs text-zinc-500">{t('tags.weak')}</p>
              <Tags tags={tags.weak_tags} tone="bad" />
            </div>
          )}
          {tags.missing_high_value_tags.length > 0 && (
            <div>
              <p className="mb-1 text-xs text-zinc-500">{t('tags.missing')}</p>
              <Tags tags={tags.missing_high_value_tags} />
            </div>
          )}
          {tags.replacements.length > 0 && (
            <ul className="space-y-1 text-xs text-zinc-500">
              {tags.replacements.map((r) => (
                <li key={`${r.remove}-${r.add}`}>
                  <span className="line-through decoration-zinc-300">{r.remove}</span>
                  {' → '}
                  <span className="font-medium text-zinc-700">{r.add}</span>
                  {' — '}
                  {r.reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-zinc-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-zinc-900">
          {t('description.heading')}
        </h3>
        {description.issues.length > 0 && (
          <>
            <p className="mb-1 mt-2 text-xs text-zinc-500">
              {t('description.missingSections')}
            </p>
            <ul className="list-inside list-disc text-sm text-zinc-700">
              {description.issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </>
        )}
        {description.recommended_additions.length > 0 && (
          <>
            <p className="mb-1 mt-3 text-xs text-zinc-500">
              {t('description.additions')}
            </p>
            <ul className="list-inside list-disc text-sm text-zinc-700">
              {description.recommended_additions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </>
        )}
        {description.issues.length === 0 &&
          description.recommended_additions.length === 0 &&
          !description.optimized_description && (
            <p className="mt-2 text-sm text-zinc-500">{t('description.allGood')}</p>
          )}
        {description.optimized_description && (
          <CopyableDescription text={description.optimized_description} />
        )}
      </section>

      {images && (images.suggestions.length > 0 || images.score !== null) && (
        <section className="rounded-xl border border-zinc-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-zinc-900">
              {t('images.heading')}
            </h3>
            {images.score !== null && (
              <span className="text-xs font-semibold tabular-nums text-zinc-500">
                {images.score}/100
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-zinc-500">{t('images.hint')}</p>
          {images.suggestions.length > 0 ? (
            <ul className="mt-3 space-y-3">
              {images.suggestions.map((s) => (
                <li
                  key={s.image_index}
                  className="rounded-lg border border-zinc-100 bg-zinc-50/60 p-3"
                >
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-400">
                    {t('images.photo', { n: s.image_index + 1 })}
                  </p>
                  <p className="text-xs text-zinc-500">
                    {t('images.current')}:{' '}
                    <span className="text-zinc-600">
                      {s.current_alt?.trim() || t('images.noAlt')}
                    </span>
                  </p>
                  <div className="mt-2">
                    <p className="mb-1 text-xs text-zinc-500">{t('images.suggested')}</p>
                    <CopyableAltText text={s.suggested_alt} />
                  </div>
                  {s.issue && <p className="mt-1 text-xs text-zinc-400">{s.issue}</p>}
                </li>
              ))}
            </ul>
          ) : (images.score ?? 0) >= 50 ? (
            <p className="mt-2 text-sm text-zinc-500">{t('images.allGood')}</p>
          ) : (
            <p className="mt-2 text-sm text-zinc-500">{t('images.needsSync')}</p>
          )}
        </section>
      )}

      {analysis.competitor_gap_summary && (
        <section className="rounded-xl border border-indigo-100 bg-indigo-50 p-4 text-sm text-indigo-900">
          <h3 className="text-sm font-semibold">{t('competitorGap')}</h3>
          <p className="mt-1">{analysis.competitor_gap_summary}</p>
        </section>
      )}
    </div>
  )
}
