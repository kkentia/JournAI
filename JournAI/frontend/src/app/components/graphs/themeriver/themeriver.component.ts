import { Component, OnInit, AfterViewInit, ViewChild, ElementRef, OnDestroy } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { GraphService, GraphView, GraphFilter } from '../graph.service';
import { Subject, takeUntil, combineLatest, distinctUntilChanged, BehaviorSubject, filter } from 'rxjs';
import { Router } from '@angular/router';

interface FlowRow { //defines structure of a single data row
  bucket_start: string;
  primary: 'joy' | 'trust' | 'fear' | 'surprise' | 'sadness' | 'disgust' | 'anger' | 'anticipation';
  intensity: number;
  reasons: string[];
}

@Component({
  selector: 'app-themeriver',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './themeriver.component.html',
  styleUrl: './themeriver.component.scss'
})
export class ThemeriverComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('riverDiv', { static: true }) riverDiv!: ElementRef<HTMLDivElement>; //tells plotly where to render the graph. gives this class access to an elem in the template

  private Plotly: any;
  private plotlyReady$ = new BehaviorSubject<boolean>(false); //true when plotly is rdy

  loading = false;
  flows: FlowRow[] = [];
  private unsubscribe$ = new Subject<void>();

  private readonly COLORS: Record<string, string> = {
    joy: '#FFD700', trust: '#2ECC71', fear: '#1E90FF', surprise: '#FF69B4',
    sadness: '#708090', disgust: '#8B0000', anger: '#FF4500', anticipation: '#FFA500'
  };
  private readonly ORDER = ['joy', 'trust', 'fear', 'surprise', 'sadness', 'disgust', 'anger', 'anticipation'] as const;

  constructor(private http: HttpClient, private graphService: GraphService, private router: Router) { }

  //hook runs once after the comp's VIEW has been init
  async ngAfterViewInit() {
    if (typeof window !== 'undefined') {
      this.Plotly = await import('plotly.js-dist-min');
      this.plotlyReady$.next(true);
    }
  }
  //hook runs once when comp is init
  ngOnInit(): void {
    //waits for the view and for Plotly to be ready.
    combineLatest([
      this.graphService.selectedView$.pipe(distinctUntilChanged()), //view
      this.graphService.filter$.pipe(distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr))), //entry id filter
      this.plotlyReady$.pipe(filter(isReady => isReady === true)) //gate
    ])
      .pipe(takeUntil(this.unsubscribe$))
      .subscribe(([view, filter]) => {
        this.fetch(view, filter);
      });
  }
  //hook for when comp is removed from the DOM.
  ngOnDestroy(): void {
    this.unsubscribe$.next();
    this.unsubscribe$.complete();
  }

  private fetch(view: GraphView, filter: GraphFilter) {
    this.loading = true;

    let params = new HttpParams().set('view', view);
    if (filter.entryId) { // entry id view
      params = params.set('entry_id', String(filter.entryId));
    } else if (filter.sessionId) { //normal selectView views
      params = params.set('session_id', String(filter.sessionId));
    }

    this.http.get<any>('http://localhost:8000/themeriver', { params })
      .subscribe({
        next: data => {
          this.flows = (Array.isArray(data?.items) ? data.items : []).map((it: any) => ({
            bucket_start: String(it.timestamp),
            primary: String(it.emotion) as FlowRow['primary'],
            intensity: Number(it.intensity) || 0,
            reasons: it.reasons || []
          }));
          this.loading = false;
          this.render(view);
        },
        error: _ => {
          this.flows = [];
          this.loading = false;
          this.render(view);
        }
      });
  }

  //renders graph using plotly based on current this.flows data
  private render(view: GraphView) {
    if (!this.Plotly || !this.riverDiv) return;

    if (!this.flows?.length) {
      this.Plotly.react(this.riverDiv.nativeElement, [], { title: 'No data for this period' });
      return;
    }

    let originalBuckets = Array.from(new Set(this.flows.map(f => f.bucket_start))).sort();

    //single data point case: create a new dp 1h later
    if (originalBuckets.length < 2) {
      if (originalBuckets.length === 1) {
          const t0 = new Date(originalBuckets[0]);
          const t1 = new Date(t0.getTime() + 60 * 60 * 1000);
          originalBuckets = [originalBuckets[0], t1.toISOString()];
      } else {
          this.Plotly.react(this.riverDiv.nativeElement, [], { title: 'Not enough data to draw a river' });
          return;
      }
    }

    const isSinglePaddedPoint = (originalBuckets.length === 2 && this.flows.length <= this.ORDER.length);

    let displayBuckets = originalBuckets;

    //NORMALIZATION OF DP
    if (!isSinglePaddedPoint) {
        const startTime = new Date(originalBuckets[0]).getTime(); //start time of data range
        const endTime = new Date(originalBuckets[originalBuckets.length - 1]).getTime();//end time of data range
        displayBuckets = [];
        const dayInMillis = 86400000; // a day in miliseconds
        for (let t = startTime; t <= endTime; t += dayInMillis) { //loop and increment by 1 day at a time
            displayBuckets.push(new Date(t).toISOString());
        }
        if (displayBuckets[displayBuckets.length - 1] !== originalBuckets[originalBuckets.length - 1]) { //ensure the last dp is included aswell
            displayBuckets.push(originalBuckets[originalBuckets.length - 1]);
        }
    }
    //LINEAR INTERPOLATION: calc the intensity foreach new day via linear interpolation
    const traces: any[] = [];
    for (const p of this.ORDER) {
      const originalPoints = originalBuckets.map(b => {
        const row = this.flows.find(f => f.bucket_start === b && f.primary === p);
        return {
          time: new Date(b).getTime(),
          value: row ? row.intensity : 0,
          reasons: row? row.reasons: []
        };
      });
      //foreach new normalized days, calc intensity
      const yValues = displayBuckets.map(b => {
        const currentTime = new Date(b).getTime();
        const p1 = [...originalPoints].reverse().find(pt => pt.time <= currentTime); //last original dp BEFORE current time
        const p2 = originalPoints.find(pt => pt.time >= currentTime); //1st original dp AFTER current time

        if (p1 && p2) { //if new dp is between 2 original dp
            if (p1.time === p2.time) return p1.value;
            const t = (currentTime - p1.time) / (p2.time - p1.time); //cal how far, as a %, the new dp is along the line between p1 and p2
            return p1.value + t * (p2.value - p1.value); //aply the % to the diff in intensity
        }
        return p1 ? p1.value : (p2 ? p2.value : 0);
      });

      //show reasons on dp hover using customdata and hovertemplate
      const customdata = displayBuckets.map(b => {
        const currentTime = new Date(b).getTime();
        const closestPoint = originalPoints.reduce((prev, curr) =>
          Math.abs(curr.time - currentTime) < Math.abs(prev.time - currentTime) ? curr : prev
        );
        return { reasons: closestPoint.reasons };

      });
      traces.push({
        type: 'scatter',
        x: displayBuckets, //normalized timeline
        y: yValues,
        mode: 'lines',
        stackgroup: 'river',
        line: { width: 1, shape: 'spline', smoothing: 1.0 },
        name: p,
        fill: 'tonexty',
        fillcolor: this.COLORS[p],
        customdata: customdata,
        hovertemplate: `<b>%{data.name}</b><br>Intensity: %{y:.0%}<br>Reasons: %{customdata.reasons}<extra></extra>`
      });
    }

    const totals = displayBuckets.map((_b, i) => traces.reduce((sum, trace) => sum + trace.y[i], 0));
    const yMax = Math.max(1, ...totals);
    const pad = yMax * 0.1;

    let tickformat: string;
    let dtick: number | string;

    switch (view) {
      case 'day':
        tickformat = '%H:%M';
        dtick = 1 * 60 * 60 * 1000; //ticks every hour
        break;
      case 'week':
        tickformat = '%b %d';
        dtick = 24 * 60 * 60 * 1000; //ticks every 24hour
        break;
      case 'month':
        tickformat = '%b %d';
        dtick = 24 * 60 * 60 * 1000 * 7; //ticks every 7days
        break;
      default:
        tickformat = '%H:%M';
        dtick = 'auto';
        break;
    }

    const layout: any = {
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      hovermode: 'x unified',
      margin: { l: 50, r: 60, t: 60, b: 60 },
      xaxis: {
        type: 'date',
        tickformat: tickformat,
        dtick: dtick,
      },
      yaxis: {
        title: 'Intensity (stacked)',
        range: [0, yMax + pad],
        fixedrange: false,
        hoverformat: '.0%'
      },
      showlegend: true,
    };

    const config = { responsive: true, displayModeBar: false };
    this.Plotly.react(this.riverDiv.nativeElement, traces, layout, config);
  }
}
