import { Component, EventEmitter, Output, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-questionnaire',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './questionnaire.component.html',
  styleUrl: './questionnaire.component.scss'
})
export class QuestionnaireComponent {
  constructor(private http: HttpClient) {}

  @Output() completed = new EventEmitter<void>();
  @Input() entryId?: number;

  phq4Questions = [
    { label: 'Feeling nervous, anxious, or on edge', value: undefined },
    { label: 'Not being able to stop or control worrying', value: undefined },
    { label: 'Feeling down, depressed, or hopeless', value: undefined },
    { label: 'Little interest or pleasure in doing things', value: undefined }
  ];

  stateFeelings = [
    { label: 'Distressed', value: undefined },
    { label: 'Irritable', value: undefined },
    { label: 'Nervous', value: undefined },
    { label: 'Scared', value: undefined },
    { label: 'Unhappy', value: undefined },
    { label: 'Upset', value: undefined },
    { label: 'Lonely', value: undefined }
  ];

  //isFormValid=false;
  submitClicked = false

  onSubmit() {
    if (this.submitClicked) return;
    this.submitClicked = true;

    const payload: any = {
      phq4_answers: this.phq4Questions.map(q => q.value),
      state_feelings: this.stateFeelings.map(f => f.value),
    };

    // only include entry_id if there is one (conversation started)
    if (this.entryId) {
      payload.entry_id = this.entryId;
    }

    this.http.post('http://localhost:8000/mood', payload).subscribe({
      next: () => this.completed.emit(),
      error: (err) => console.error('Failed to submit mood data:', err)
    });
  }
  /*
  onSkip() {
    this.completed.emit(); // skip validation and submit
  }
  */

}
