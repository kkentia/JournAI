import { Component, OnInit, OnDestroy } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { getISOWeek, parseISO, startOfWeek, endOfWeek, format } from 'date-fns';
import { GraphService, GraphView, GraphFilter } from '../../graph.service';
import { Subject, takeUntil, combineLatest, distinctUntilChanged } from 'rxjs';



interface Activity {
  name: string;
  count?: number;
  mood?: number;
}

@Component({
  selector: 'app-histogram',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './histogram.component.html',
  styleUrl: './histogram.component.scss'
})
export class HistogramComponent implements OnInit, OnDestroy {
  data: { day: string, activities: Activity[] }[] = [];

  totalBarHeight = 200;

  weeks: string[] = [];
  selectedWeek: string = '';
  weekGroupedData: { [weekKey: string]: { day: string; activities: Activity[] }[] } = {};

  weekStart: Date = new Date();
  weekEnd: Date = new Date();

  selectedNames = new Set<string>();  //activity labels selected by user
  mergeTarget = '';
  isMerging = false;

  private destroy$ = new Subject<void>();

  constructor(private http: HttpClient, private graphService: GraphService) { }

  // -----------------------------------week-selector-----------------------------------
  get weekLabel(): string {
    if (!this.selectedWeek && this.weeks.length === 0) return "No activity data available";
    if (!this.selectedWeek) return "Loading...";
    return `${format(this.weekStart, 'MMM d')} - ${format(this.weekEnd, 'MMM d, yyyy')}`;
  }
  prevWeek() {
    if (!this.selectedWeek) return;
    const idx = this.weeks.indexOf(this.selectedWeek);
    if (idx < this.weeks.length - 1) {
      this.selectedWeek = this.weeks[idx + 1];
      this.onWeekChange();
    }
  }
  nextWeek() {
    if (!this.selectedWeek) return;
    const idx = this.weeks.indexOf(this.selectedWeek);
    if (idx > 0) {
      this.selectedWeek = this.weeks[idx - 1];
      this.onWeekChange();
    }
  }
  updateWeekRange() {
    const daysInWeek = this.weekGroupedData[this.selectedWeek];
    if (daysInWeek && daysInWeek.length > 0) {
      const anyDay = daysInWeek.find(d => d.day)?.day;
      if (anyDay) {
        const dateObj = parseISO(anyDay);
        this.weekStart = startOfWeek(dateObj, { weekStartsOn: 1 });
        this.weekEnd = endOfWeek(dateObj, { weekStartsOn: 1 });
      }
    }
  }
  // -----------------------------------week-selector-----------------------------------

  ngOnInit() {
    combineLatest([
      this.graphService.selectedView$.pipe(distinctUntilChanged()),
      this.graphService.filter$.pipe(distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr)))
    ])
      .pipe(takeUntil(this.destroy$))
      .subscribe(([view, filter]) => {
        this.fetchHistogram(view, filter);
      });
  }

  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
  }

  fetchHistogram(view: GraphView, filter: GraphFilter) {
    let params = new HttpParams().set('view', view);
    if (filter.entryId) {
      params = params.set('entry_id', String(filter.entryId));
    } else if (filter.sessionId) {
      params = params.set('session_id', String(filter.sessionId));
    }

    this.http.get<any[]>('http://localhost:8000/metrics/histogram', { params })
      .subscribe(res => {
        const data = Array.isArray(res) ? res : [];

        if (data.length === 0) {
            this.weekGroupedData = {};
            this.weeks = [];
            this.selectedWeek = '';
            this.data = Array.from({ length: 7 }, (_, i) => ({ day: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][i], activities: [] }));
            return;
        }

        const groupedByWeek: { [weekKey: string]: { day: string; activities: any[] }[] } = {};

        data.forEach(day => {
          const dateObj = parseISO(day.day);
          if (isNaN(dateObj.getTime())) return;

          const weekNumber = getISOWeek(dateObj);
          const year = dateObj.getFullYear();
          const weekKey = `${year}-W${weekNumber}`;
          const weekdayIndex = (dateObj.getDay() + 6) % 7; // monday=0

          if (!groupedByWeek[weekKey]) {
            groupedByWeek[weekKey] = Array.from({ length: 7 }, () => ({ day: '', activities: [] }));
          }

          groupedByWeek[weekKey][weekdayIndex] = {
            day: day.day,
            //sort by count
            activities: (day.activities || []).sort(
              (a: { count?: number }, b: { count?: number }) => (b.count ?? 0) - (a.count ?? 0)
            )
          };
        });

        this.weekGroupedData = groupedByWeek;
        this.weeks = Object.keys(groupedByWeek).sort((a, b) => b.localeCompare(a));

        if (filter.entryId && data.length > 0) {
            const dateObj = parseISO(data[0].day);
            const weekNumber = getISOWeek(dateObj);
            const year = dateObj.getFullYear();
            this.selectedWeek = `${year}-W${weekNumber}`;
        } else {
            this.selectedWeek = this.weeks[0] || '';
        }

        this.onWeekChange();
      });
  }

  onWeekChange() {
    if (!this.selectedWeek || !this.weekGroupedData[this.selectedWeek]) {
      this.data = Array.from({ length: 7 }, (_, i) => ({ day: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][i], activities: [] }));
      this.updateWeekRange();
      return;
    };

    const weekData = this.weekGroupedData[this.selectedWeek];
    const weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

    this.data = weekdays.map((label, i) => ({
      day: label,
      activities: weekData[i]?.activities || []
    }));

    this.updateWeekRange();
  }

  getTotalActivitiesSafe(activities: { name: string; count?: number }[]): number {
    if (!activities) return 0;
    return activities.reduce((sum, a) => sum + (a.count ?? 0), 0);
  }

  getMoodColor(mood: number | null | undefined): string {
    const m = Math.max(1, Math.min(10, (mood ?? 5))); // 1..10, default 5=neutral
    const hue = (m - 1) * (120 / 9); // 0=red, 120=green
    return `hsl(${hue}, 70%, 50%)`;
  }
  isSelected(name: string): boolean {
    return this.selectedNames.has(name.toLowerCase());
  }
  toggleSelect(name: string) {
    const key = name.toLowerCase();
    if (this.selectedNames.has(key)) {
      this.selectedNames.delete(key);
    } else {
      this.selectedNames.add(key);
    }
  }
  clearSelection() {
    this.selectedNames.clear();
    this.mergeTarget = '';
  }

  // --------merge ----------
  canMerge(): boolean {
    return this.selectedNames.size >= 2 && this.mergeTarget.trim().length > 0 && !this.isMerging;
  }
  mergeSelected() {
    if (!this.canMerge()) return;
    this.isMerging = true;

    const body = { sources: Array.from(this.selectedNames), target: this.mergeTarget.trim() };
    this.http.post('http://localhost:8000/metrics/activities/merge', body)
      .subscribe({
        next: () => {
          this.isMerging = false;
          this.clearSelection();
          const currentView = this.graphService.getCurrentView();
          const currentFilter = this.graphService.getCurrentFilter();
          this.fetchHistogram(currentView, currentFilter);
        },
        error: (err) => { console.error('Merge failed:', err); this.isMerging = false; }
      });
  }
}
