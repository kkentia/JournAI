import { Component, OnInit, AfterViewInit, ViewChild, ElementRef, OnDestroy } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { GraphService, GraphView, GraphFilter } from '../../graphs/graph.service';
import { Subject, takeUntil, combineLatest, distinctUntilChanged } from 'rxjs';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { CommonModule } from '@angular/common';

type Source = 'ai' | 'user';

interface PlutchikPoint {
  entry_id: number;
  session_id: number;
  source: Source;
  primary: 'joy' | 'trust' | 'fear' | 'surprise' | 'sadness' | 'disgust' | 'anger' | 'anticipation';
  level: 1 | 2 | 3;
  intensity: number;     // 0..1
  sub_label: string;
  confidence?: number | null;
  timestamp: string;
}

interface PlutchikDyad {
  entry_id: number;
  session_id: number;
  source: Source;
  primary_a: PlutchikPoint['primary'];
  primary_b: PlutchikPoint['primary'];
  dyad_label: string;
  weight: number;      // 0..1
  confidence?: number | null;
  timestamp: string;
}

@Component({
  selector: 'app-plutchik-wheel',
  templateUrl: './plutchik-graph.component.html',
  styleUrls: ['./plutchik-graph.component.scss'],
  standalone: true,
  imports: [CommonModule]
})
export class PlutchikWheelComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('wheelDiv', { static: true }) wheelDiv!: ElementRef<HTMLDivElement>;
  private Plotly: any;
  private plotlyReady$ = new Subject<void>();

  private unsubscribe$ = new Subject<void>();

  showAI = true;
  showUser = true;

  dataAI: PlutchikPoint[] = [];
  dataUser: PlutchikPoint[] = [];

  dyadsAI: PlutchikDyad[] = [];
  dyadsUser: PlutchikDyad[] = [];

  // canonical angles/colors for primaries (clockwise, 0degrees at +x axis)
  private readonly ANGLES: Record<string, number> = {
    fear: 0, trust: 45, joy: 90, anticipation: 135,
    anger: 180, disgust: 225, sadness: 270, surprise: 315
  };

  private clickBound = false;
  constructor(private http: HttpClient, private graphService: GraphService) { }

  ngOnInit() {
    combineLatest([
      this.graphService.selectedView$.pipe(distinctUntilChanged()),
      this.graphService.filter$.pipe(distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr))),
      this.plotlyReady$
    ])
    .pipe(takeUntil(this.unsubscribe$))
    .subscribe(([view, filter]) => {
      this.fetchData(view, filter);
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

  onToggleAI() { this.showAI = !this.showAI; this.render(); }
  onToggleUser() { this.showUser = !this.showUser; this.render(); }

  // --- data fetching (primaries + dyads) ------------------------------------
  private fetchData(view: GraphView, filter: GraphFilter) {
    const p = (src: 'ai' | 'user') => {
      let params = new HttpParams().set('view', view).set('source', src);
      if (filter.entryId) {
        params = params.set('entry_id', String(filter.entryId));
      } else if (filter.sessionId) {
        params = params.set('session_id', String(filter.sessionId));
      }
      return params;
    };

    const primAI$ = this.http.get<PlutchikPoint[]>('http://localhost:8000/plutchik-results', { params: p('ai') }).pipe(catchError(() => of([])));
    const primUser$ = this.http.get<PlutchikPoint[]>('http://localhost:8000/plutchik-results', { params: p('user') }).pipe(catchError(() => of([])));
    const dyadAI$ = this.http.get<PlutchikDyad[]>('http://localhost:8000/plutchik-dyads', { params: p('ai') }).pipe(catchError(() => of([])));
    const dyadUser$ = this.http.get<PlutchikDyad[]>('http://localhost:8000/plutchik-dyads', { params: p('user') }).pipe(catchError(() => of([])));

    forkJoin([primAI$, primUser$, dyadAI$, dyadUser$]).subscribe(([ai, user, dai, duser]) => {
      this.dataAI = ai ?? [];
      this.dataUser = user ?? [];
      this.dyadsAI = dai ?? [];
      this.dyadsUser = duser ?? [];
      this.render();
    });
  }

  // --- plotting --------------------------------------------------------------
  private render() {
    if (!this.Plotly || !this.wheelDiv) return;

    const traces: any[] = [];

    // primaries
    if (this.showAI && this.dataAI.length) traces.push(this.buildPrimaryTrace(this.dataAI, 'AI Assessment', 12, 'rgb(255, 0, 0)'));
    if (this.showUser && this.dataUser.length) traces.push(this.buildPrimaryTrace(this.dataUser, 'User Assessment', 10, 'rgb(54, 162, 235)'));

    // dyad stars
    if (this.showAI && this.dyadsAI.length) traces.push(this.buildDyadMarkers(this.dyadsAI, 'AI Dyads', 'star-square', 'rgb(255, 0, 0)'));
    if (this.showUser && this.dyadsUser.length) traces.push(this.buildDyadMarkers(this.dyadsUser, 'User Dyads', 'star-square', 'rgb(54, 162, 235)'));

    // fallback so axes appear
    if (traces.length === 0) {
      traces.push({ type: 'scatterpolar', r: [0], theta: [0], mode: 'markers', marker: { size: 0 }, name: 'No data' });
    }

    const layout: any = {
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      margin: { l: 40, r: 40, t: 60, b: 40 },
      showlegend: true,
      polar: {
        radialaxis: {
          visible: true,
          range: [0, 3],
          tickvals: [1, 2, 3],
          ticktext: ['low', 'med', 'high']
        },
        angularaxis: {
          direction: 'clockwise',
          tickvals: Object.values(this.ANGLES),
          ticktext: ['fear', 'trust', 'joy', 'anticipation', 'anger', 'disgust', 'sadness', 'surprise'],
          rotation: 0
        }
      }
    };

    const config = { responsive: true, displayModeBar: false };
    this.Plotly.react(this.wheelDiv.nativeElement, traces, layout, config);

    //filter
    if (!this.clickBound) {
      this.clickBound = true;
      (this.wheelDiv.nativeElement as any).on('plotly_click', (ev: any) => {
        const pt = ev?.points?.[0];
        const cd = pt?.customdata as { entry_id?: number | null; session_id?: number | null } | undefined;
        if (!cd) return; //cd = custom data;
      });
    }
  }

  private buildPrimaryTrace(data: PlutchikPoint[], name: string, size = 12, color: string) {
    const r = data.map(d => Math.max(0, Math.min(1, d.intensity)) * 3);
    const theta = data.map(d => this.ANGLES[d.primary]);
    //below: what we see on hover datapoint
    const text = data.map(d => `Emotion: ${d.sub_label}<br>Intensity: ${(d.intensity*100).toFixed(0)}%`);

    return {
      type: 'scatterpolar',
      r, theta, text,
      customdata: data.map(d => ({ entry_id: d.entry_id, session_id: d.session_id })),
      mode: 'markers',
      marker: { size, color: color, line: { width: 1, color: '#333' } },
      hovertemplate: '%{text}<extra></extra>', //what we see on hover
      name
    };
  }

  private midAngle(aDeg: number, bDeg: number): number {
    let diff = bDeg - aDeg;
    if (diff > 180) diff -= 360;
    if (diff < -180) diff += 360;
    return aDeg + diff / 2;
  }

  private buildDyadMarkers(dyads: PlutchikDyad[], name: string, symbol: any = 'star', color: string) {
    const r = dyads.map(d => Math.max(0, Math.min(1, d.weight)) * 3);
    const theta = dyads.map(d => this.midAngle(this.ANGLES[d.primary_a], this.ANGLES[d.primary_b]));
    const text = dyads.map(d => `${d.dyad_label} = ${d.primary_a}+${d.primary_b}<br>Intensity: ${(d.weight * 100).toFixed(0)}%`);

    return {
      type: 'scatterpolar',
      r, theta, text,
      customdata: dyads.map(d => ({ entry_id: d.entry_id, session_id: d.session_id })),

      mode: 'markers',
      marker: { size: 14, symbol, color, line: { width: 1 } },
      hovertemplate: '%{text}<extra></extra>',
      name
    };
  }

  private buildDyadLines(dyads: PlutchikDyad[], source: Source, dash: any = 'solid') {
    const evts = (source === 'ai') ? this.dataAI : this.dataUser;
    const lines: any[] = [];

    for (const d of dyads) {
      const aEvt = evts.find(e => e.primary === d.primary_a);
      const bEvt = evts.find(e => e.primary === d.primary_b);
      if (!aEvt || !bEvt) continue;

      const r1 = (aEvt ? Math.max(0, Math.min(1, aEvt.intensity)) * 3 : 0);
      const r2 = (bEvt ? Math.max(0, Math.min(1, bEvt.intensity)) * 3 : 0);

      lines.push({
        type: 'scatterpolar',
        r: [r1, r2],
        theta: [this.ANGLES[d.primary_a], this.ANGLES[d.primary_b]],
        mode: 'lines',
        line: { width: 1, dash, color: source === 'ai' ? 'rgb(255, 0, 0)' : 'rgb(54, 162, 235)' },
        showlegend: false
      });
    }
    return lines;
  }
}
