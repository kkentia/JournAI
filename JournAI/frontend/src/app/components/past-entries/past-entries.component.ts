import { Component, OnInit } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatToolbarModule } from '@angular/material/toolbar';
import { Router } from '@angular/router';

interface Message {
  sender: 'user' | 'bot';
  content: string;
  timestamp: string;
}

interface Entry {
  entry_id: number;
  title: string;
  timestamp: string;
  messages: Message[];
}

@Component({
  selector: 'app-past-entries',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatCardModule, MatToolbarModule],
  templateUrl: './past-entries.component.html',
  styleUrl: './past-entries.component.scss'
})
export class PastEntriesComponent implements OnInit {
  constructor(private http: HttpClient, private router: Router) {}

  chatEntries: Entry[] = [];
  selectedEntry: Entry | null = null;
  showConfirmDialog = false;
  entryToDelete: Entry | null = null;

  ngOnInit() {
    this.fetchEntries();
  }

  goBack() {
  // this.location.back(); not good because if prev page is google, it will go to google
    this.router.navigate(['/dashboard']);
  }

  fetchEntries() {
    this.http.get<Entry[]>('http://localhost:8000/entries').subscribe(
      (data) => {
        // keep only non-empty titles
        this.chatEntries = (data || []).filter(e => e.title !== 'empty_entry');
      },
      (error) => console.error('Error fetching entries:', error)
    );
  }

  openPopup(entry: Entry) {
    this.selectedEntry = entry;
  }

  closePopup() {
    this.selectedEntry = null;
  }

 summarizeEntry(entryId: number) {
    // go to graphs page w the entry_id in the URL -> graphs fetch only that entry
    this.router.navigate(['/graphs'], { queryParams: { entry_id: entryId }, replaceUrl: false });
  }

    renameEntry(entry: Entry) {
    const newTitle = prompt('Enter a new title for this entry:', entry.title); //browser prompt

    if (newTitle && newTitle.trim() !== '') {
      const updatedTitle = newTitle.trim();
      
      this.http.put(`http://localhost:8000/entries/${entry.entry_id}/rename`, { new_title: updatedTitle })
        .subscribe({
          next: () => {
            //update title in the local array so the UI changes instantly
            const entryInList = this.chatEntries.find(e => e.entry_id === entry.entry_id);
            if (entryInList) {
              entryInList.title = updatedTitle;
            }
          },
          error: (error) => console.error('Error renaming entry:', error)
        });
    }
  }

  confirmDeleteEntry() {
    if (!this.entryToDelete) return;
    this.http.delete(`http://localhost:8000/entries/${this.entryToDelete.entry_id}`).subscribe(
      () => {
        this.chatEntries = this.chatEntries.filter(e => e.entry_id !== this.entryToDelete!.entry_id);
        this.showConfirmDialog = false;
        this.entryToDelete = null;
      },
      (error) => console.error('Error deleting entry:', error)
    );
  }

  deleteData(entry: Entry) {
    this.entryToDelete = entry;
    this.showConfirmDialog = true;
  }

  cancelDelete() {
    this.showConfirmDialog = false;
  }
}
