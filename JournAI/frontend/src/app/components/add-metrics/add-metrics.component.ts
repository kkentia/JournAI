import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms'; //for ngModel
import { CommonModule } from '@angular/common'; //for ngIf
import {MatToolbarModule} from '@angular/material/toolbar';
import { Router } from '@angular/router';




type Tab = 'activities' | 'quiz' | 'plutchik';

const PLUTCHIK: Record<string, Record<1 | 2 | 3, string> > = {
  joy:          { 1: 'serenity',     2: 'joy',          3: 'ecstasy' },
  trust:        { 1: 'acceptance',   2: 'trust',        3: 'admiration' },
  fear:         { 1: 'apprehension', 2: 'fear',         3: 'terror' },
  surprise:     { 1: 'distraction',  2: 'surprise',     3: 'amazement' },
  sadness:      { 1: 'pensiveness',  2: 'sadness',      3: 'grief' },
  disgust:      { 1: 'boredom',      2: 'disgust',      3: 'loathing' },
  anger:        { 1: 'annoyance',    2: 'anger',        3: 'rage' },
  anticipation: { 1: 'interest',     2: 'anticipation', 3: 'vigilance' },
};

interface PlutchikRow {
  primary: 'joy'|'trust'|'fear'|'surprise'|'sadness'|'disgust'|'anger'|'anticipation';
  intensity: number;   // 0..1
  level: 1|2|3;
  subLabel: string;   // read only in UI
}

@Component({
  selector: 'app-add-entry',
  standalone: true,
  imports: [FormsModule, CommonModule,MatToolbarModule],
  templateUrl: './add-metrics.component.html',
  styleUrl: './add-metrics.component.scss'
})
export class AddMetricsComponent {


  constructor(private http: HttpClient, private router:Router) {}

  activeTab: Tab = 'activities';

    goBack() {
  this.router.navigate(['/dashboard']);

}

  // -------------------- activities (inside metrics: activity tag) --------------------
  actForm = {
    description: '',
    comment: '',
    rating: null as number|null
  };

  submitActivity() {
    if (!this.actForm.description || !this.actForm.rating) return;
    const payload = {
      tag: 'activity',
      description: this.actForm.description.trim(),
      comment: (this.actForm.comment || '').trim(),
      rating: Number(this.actForm.rating),
      entry_id: null
    };
    this.http.post('http://localhost:8000/submit-metric', payload)
      .subscribe(() => {
        this.actForm = { description: '', comment: '', rating: null };
        alert('Activity saved ');
      }, err => alert('Failed to save activity: ' + (err?.error?.detail || '')));
  }

  // -------------------- quiz / spider (metrics: phq4 -> f1..f7) --------------------
  spiderLabels = [
    { key: 'f1', label: 'Distressed' },
    { key: 'f2', label: 'Irritable'  },
    { key: 'f3', label: 'Nervous'    },
    { key: 'f4', label: 'Scared'     },
    { key: 'f5', label: 'Unhappy'    },
    { key: 'f6', label: 'Upset'      },
    { key: 'f7', label: 'Lonely'     },
  ];
  quizRatings: Record<string, number|null> = {
    f1:null,f2:null,f3:null,f4:null,f5:null,f6:null,f7:null
  };

  submitQuiz() {
    const posts = this.spiderLabels
      .filter(ax => this.quizRatings[ax.key] != null)
      .map(ax => this.http.post('http://localhost:8000/submit-metric', {
        tag: 'quiz',
        description: ax.key,
        comment: ax.label,
        rating: Number(this.quizRatings[ax.key]),
        entry_id: null
      }));

    if (posts.length === 0) {
      alert('Add at least one rating.');
      return;
    }
    posts.forEach(req => req.subscribe({
      error: err => console.error(err)
    }));
    alert('Quiz ratings saved.');
    this.quizRatings = { f1:null,f2:null,f3:null,f4:null,f5:null,f6:null,f7:null };
  }

  // -------------------- valence & ar. --------------------


  // no user insertion because i think it would be too ambiguous for user to self-evaluate "arousal" and "valence"

  // -------------------- plutchik --------------------
plutchikRows: PlutchikRow[] = [
  { primary: 'joy', intensity: 0.5, level: 2, subLabel: PLUTCHIK['joy'][2] },
];

addPlutchikRow() {
  this.plutchikRows.push({ primary: 'joy', intensity: 0.5, level: 2, subLabel: PLUTCHIK['joy'][2] });
}
removeRow(i: number) { this.plutchikRows.splice(i, 1); }

clamp01(v: number) { return Math.max(0, Math.min(1, v)); }

updateLevel(r: PlutchikRow) {
  const x = this.clamp01(r.intensity);
  r.level = (x < 1/3) ? 1 : (x < 2/3 ? 2 : 3) as 1|2|3;
  r.subLabel = PLUTCHIK[r.primary][r.level];
}

onPrimaryChange(r: PlutchikRow) {
  r.level = (r.level === 1 || r.level === 2 || r.level === 3) ? r.level : 2;
  r.subLabel = PLUTCHIK[r.primary][r.level];
}
onLevelChange(r: PlutchikRow) {
  r.level = (r.level < 1 ? 1 : r.level > 3 ? 3 : r.level) as 1|2|3;
  r.subLabel = PLUTCHIK[r.primary][r.level];
}

submitPlutchik() {
  const emotions = this.plutchikRows.map(r => ({
    primary_emotion: r.primary,                 // one of the 8 primaries
    intensity: this.clamp01(r.intensity),
    level: r.level
  }));

  this.http.post('http://localhost:8000/manual/plutchik', { emotions })
    .subscribe(
      () => alert('Plutchik events saved'),
      err => alert('Failed to save Plutchik: ' + (err?.error?.detail || err?.error || ''))
    );
}
}
