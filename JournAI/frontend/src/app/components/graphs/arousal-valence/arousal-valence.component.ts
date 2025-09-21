
import { Component, OnInit, AfterViewInit, ViewChild, ElementRef, OnDestroy } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { GraphService, GraphView, GraphFilter } from '../../graphs/graph.service';
import { Subject, takeUntil, combineLatest, distinctUntilChanged } from 'rxjs';
import { CommonModule } from '@angular/common';

interface AnalysisPoint {
  entry_id: number;
  session_id: number;
  valence: number; // -1 to 1
  arousal: number; // 0 to 1
  primary_emotion: string;
  secondary_emotion: string;
  activity_tags: string[];
  timestamp: string;
}

@Component({
  selector: 'app-arousal-valence',
  templateUrl: './arousal-valence.component.html',
  styleUrls: ['./arousal-valence.component.scss'],
  standalone: true,
  imports: [CommonModule]
})
export class ArousalValenceComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('vaDiv', { static: true }) plotDiv!: ElementRef<HTMLDivElement>;
  private Plotly: any;
  private plotlyReady$ = new Subject<void>();

  dataPoints: AnalysisPoint[] = [];
  private unsubscribe$ = new Subject<void>();

  constructor(private http: HttpClient, private graphService: GraphService) {}

  ngOnInit() {
    combineLatest([
      this.graphService.selectedView$.pipe(distinctUntilChanged()),
      this.graphService.filter$.pipe(distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr))),
      this.plotlyReady$
    ])
    .pipe(takeUntil(this.unsubscribe$))
    .subscribe(([view, filter]) => {
      this.fetchAnalysisData(view, filter);
    });
  }

  ngOnDestroy(): void {
    this.unsubscribe$.next();
    this.unsubscribe$.complete();
  }

  async ngAfterViewInit() {
    if (typeof window !== 'undefined') {
      this.Plotly = await import('plotly.js-dist-min');
      this.plotlyReady$.next();
      this.plotlyReady$.complete();
    }
  }

  private fetchAnalysisData(view: GraphView, filter: GraphFilter) {
    let params = new HttpParams().set('view', view);
    if (filter.entryId) {
      params = params.set('entry_id', String(filter.entryId));
    } else if (filter.sessionId) {
      params = params.set('session_id', String(filter.sessionId));
    }

    this.http.get<AnalysisPoint[]>("http://localhost:8000/va-results", { params }).subscribe({
      next: (data) => {
        this.dataPoints = data ?? [];
        this.render();
      },
      error: (err) => console.error("Failed to fetch analysis data", err)
    });
  }

  private render() {
    if (!this.Plotly || !this.plotDiv) return;

    // ---- aggregate identical valence/arousal pairs, but keep IDs per bucket ----
    type Bucket = {
      x: number;
      y: number;
      count: number;
      texts: string[];
      color: string;
      ids: Array<{ entry_id: number | null; session_id: number | null; timestamp: string }>;
    };

    const buckets = new Map<string, Bucket>();

    for (const dp of this.dataPoints) {
      const key = String(dp.valence) + '|' + String(dp.arousal);
      const txt =
        `Emotions: ${dp.primary_emotion}${dp.secondary_emotion ? ', ' + dp.secondary_emotion : ''}` +
        (dp.activity_tags?.length ? ` <br>Activities: ${dp.activity_tags.join(', ')}` : '');
      const color = this.mapEmotionToColor(dp.primary_emotion);

      const existing = buckets.get(key);
      if (existing) {
        existing.count += 1;
        existing.texts.push(txt);
        existing.ids.push({
          entry_id: dp.entry_id ?? null,
          session_id: dp.session_id ?? null,
          timestamp: dp.timestamp,
        });
      } else {
        buckets.set(key, {
          x: dp.valence,
          y: dp.arousal,
          count: 1,
          texts: [txt],
          color,
          ids: [{
            entry_id: dp.entry_id ?? null,
            session_id: dp.session_id ?? null,
            timestamp: dp.timestamp,
          }],
        });
      }
    }

    //build arrays for Plotly
    const xs: number[] = [];
    const ys: number[] = [];
    const sizes: number[] = [];
    const texts: string[] = [];
    const colors: string[] = [];
    const custom: Array<Array<{ entry_id: number | null; session_id: number | null; timestamp: string }>> = [];

    for (const b of buckets.values()) {
      xs.push(b.x);
      ys.push(b.y);
      // bubble size grows with count (log scale to avoid huge circles)
      sizes.push(10 + 6 * Math.log2(1 + b.count));
      colors.push(b.color);
      texts.push(`${b.texts[0]}${b.count > 1 ? `\n(+${b.count - 1} more)` : ''}`);
      custom.push(b.ids); //attach ids for this bubble
    }

    const trace = {
      x: xs,
      y: ys,
      text: texts,
      customdata: custom, //carry id list per bubble
      mode: 'markers',
      type: 'scatter' as const,
      marker: { size: sizes, line: { width: 1, color: '#333' }, color: colors, opacity: 1 },
      hovertemplate: 'Valence: %{x:.2f}<br>Arousal: %{y:.2f}<br>%{text}<extra></extra>',
    };

    const midA = 0.5;
    const layout: any = {
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      margin: { l: 60, r: 60, t: 60, b: 60 },
      xaxis: { title: { text: 'Valence' }, range: [-1, 1], tickvals: [-1, 0, 1], zeroline: true, zerolinewidth: 2, showline: true, linewidth: 1 },
      yaxis: { title: { text: 'Arousal' }, range: [0, 1], tickvals: [0, 0.5, 1], zeroline: false, showline: true, linewidth: 1 },
      shapes: [
        { type: 'rect', x0: -1, x1: 0, y0: midA, y1: 1, fillcolor: '#ff9292ff', opacity: 0.4, line: { width: 0 } },
        { type: 'rect', x0:  0, x1: 1, y0: midA, y1: 1, fillcolor: '#fffaa1ff', opacity: 0.4, line: { width: 0 } },
        { type: 'rect', x0: -1, x1: 0, y0: 0,    y1: midA, fillcolor: '#aed2ffff', opacity: 0.4, line: { width: 0 } },
        { type: 'rect', x0:  0, x1: 1, y0: 0,    y1: midA, fillcolor: '#ffa2f9ff', opacity: 0.4, line: { width: 0 } },
        { type: 'line', x0: -1, x1: 1, y0: midA, y1: midA, line: { width: 2, color: '#666' } }
      ],
      annotations: [
        { x: -1, y: 1.04, xref: 'x', yref: 'paper', text: 'Unpleasant', showarrow: false, xanchor: 'left' },
        { x:  1, y: 1.04, xref: 'x', yref: 'paper', text: 'Pleasant',   showarrow: false, xanchor: 'right' },
        { x:  1.04, y: 1, xref: 'paper', yref: 'y', text: 'High Arousal', showarrow: false, textangle: 90, yanchor: 'top' },
        { x:  1.04, y: 0, xref: 'paper', yref: 'y', text: 'Low Arousal',  showarrow: false, textangle: 90, yanchor: 'bottom' }
      ],
      hovermode: 'closest'
    };

    const config = { responsive: true, displayModeBar: false };
    const el = this.plotDiv.nativeElement;

    this.Plotly.react(el, [trace], layout, config);
  }

  //------------------- helpers ------------------
  mapEmotionToColor(emotion: string): string {
    switch (emotion.toLowerCase()) {
      case 'joy': return '#FFD700';
      case 'anger': return '#FF4500';
      case 'sadness': return '#1E90FF';
      case 'fear': return '#800080';
      case 'disgust': return '#008000';
      case 'surprise': return '#FF69B4';
      default: return '#ffffffff';
    }
  }
}
