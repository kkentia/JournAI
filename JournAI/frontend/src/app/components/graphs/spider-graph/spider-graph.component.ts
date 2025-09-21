import { Component, AfterViewInit, Input, ViewChild, ElementRef, Inject, PLATFORM_ID, OnDestroy, OnInit } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Chart, registerables } from 'chart.js/auto';
import { HttpClient, HttpParams } from '@angular/common/http';
import { GraphService, GraphView, GraphFilter } from '../graph.service';
import { Subject, takeUntil, combineLatest, distinctUntilChanged } from 'rxjs';

@Component({
  selector: 'app-spider-graph',
  standalone: true,
  templateUrl: './spider-graph.component.html',
  styleUrl: './spider-graph.component.scss'
})
export class SpiderGraphComponent implements OnInit, AfterViewInit, OnDestroy {
  @Input() canvasId = 'radarChart';
  @ViewChild('radarCanvas', { static: true }) canvasRef!: ElementRef<HTMLCanvasElement>;

  private chart?: Chart;
  private unsubscribe$ = new Subject<void>();

  constructor(
    private http: HttpClient,
    private graphService: GraphService,
    @Inject(PLATFORM_ID) private platformId: Object
  ) { }

  ngOnInit(): void {
    // re fetch on view change
    combineLatest([
      this.graphService.selectedView$.pipe(distinctUntilChanged()),
      this.graphService.filter$.pipe(distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr)))
    ])
      .pipe(takeUntil(this.unsubscribe$))
      .subscribe(([view, filter]) => {
        this.fetchData(view, filter);
      });
  }

  ngAfterViewInit() {
    if (!isPlatformBrowser(this.platformId)) return;
    Chart.register(...registerables);
  }

  ngOnDestroy(): void {
    this.unsubscribe$.next();
    this.unsubscribe$.complete();
    if (this.chart) this.chart.destroy();
  }

  fetchData(view: GraphView, filter: GraphFilter) {
    if (!isPlatformBrowser(this.platformId)) return;

    const canvas = this.canvasRef?.nativeElement;
    if (!canvas) return;

    let params = new HttpParams().set('view', view);
    if (filter.entryId) {
      params = params.set('entry_id', String(filter.entryId));
    } else if (filter.sessionId) {
      params = params.set('session_id', String(filter.sessionId));
    }

    this.http.get<any[]>('http://localhost:8000/metrics/spider-results', { params })
      .subscribe(data => {
        const axisOrder = ['f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7'];

        // helpers to pick a row per axis/source
        const pick = (src: 'user' | 'ai', desc: string) => {
          const row = data.find(x => String(x.source).toLowerCase() === src && x.description === desc);
          return {
            rating: row?.rating ?? 0,
            entryId: (row?.entry_id ?? null) as number | null,
            sessionId: (row?.session_id ?? null) as number | null,
          };
        };

        const userRatings: number[] = [];
        const aiRatings: number[] = [];

        for (const d of axisOrder) {
          const u = pick('user', d);
          const a = pick('ai', d);
          userRatings.push(u.rating);
          aiRatings.push(a.rating);
        }

        if (this.chart) this.chart.destroy();

        this.chart = new Chart(canvas, {
          type: 'radar',
          data: {
            labels: ['distressed', 'irritable', 'nervous', 'scared', 'unhappy', 'upset', 'lonely'],
            datasets: [
              {
                label: 'self assessment',
                data: userRatings,
                fill: true,
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderColor: 'rgb(54, 162, 235)',
                pointBackgroundColor: 'rgb(54, 162, 235)',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: 'rgb(54, 162, 235)',
              },
              {
                label: 'AI assessment',
                data: aiRatings,
                fill: true,
                backgroundColor: 'rgba(255, 0, 0, 0.2)',
                borderColor: 'rgb(255, 0, 0)',
                pointBackgroundColor: 'rgb(255, 0, 0)',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: 'rgb(255, 0, 0)',
              },
            ],
          },
          options: {
            responsive: true,
            scales: { r: { min: 0, max: 10, ticks: { stepSize: 1 }, pointLabels: { font: { size: 14 } } } },
            plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 20, padding: 25 } } },
            onClick: (_evt, activeEls) => {
              if (!activeEls || !activeEls.length) return;
            },
          },
        });
      }, err => console.error('Failed to fetch spider results', err));
  }
}