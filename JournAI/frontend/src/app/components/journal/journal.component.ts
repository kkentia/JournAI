import { Component,ElementRef, ViewChild, Input, Output, EventEmitter } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {MatToolbarModule} from '@angular/material/toolbar';
import { Location } from '@angular/common';
import { BaseComponent } from '../base/base.component';

import { QuestionnaireComponent } from '../questionnaire/questionnaire.component';
import { ArousalValenceComponent } from '../graphs/arousal-valence/arousal-valence.component';
import * as Plotly from 'plotly.js-dist-min';


@Component({
  selector: 'app-journal',
  standalone: true,
  imports: [CommonModule, FormsModule, QuestionnaireComponent,MatToolbarModule],
  templateUrl: './journal.component.html',
  styleUrl: './journal.component.scss'
})
export class JournalComponent extends BaseComponent {
  @ViewChild('messagesContainer') messagesContainer!: ElementRef;
  @Input() entryId?: number; // or !
  isWaitingForBot = false;
  private userAtBottom = true;
  journalText: string = '';
  sessionActive: boolean = false;
  botRepliesEnabled: boolean = false; // default: AI replies are off
  ngOnInit() {
    // chat-app auto scroll
    setTimeout(() => {
      if (this.messagesContainer) {
        this.messagesContainer.nativeElement.addEventListener('scroll', () => {
          const elem = this.messagesContainer.nativeElement;
          const threshold = 5;
          this.userAtBottom = elem.scrollHeight - elem.scrollTop - elem.clientHeight <= threshold;
        });
      }
    });
  }
  questionnaireDone: boolean = false;
  userMessage: string = '';
  chatHistory: {
    user: string,
    bot?: string,
  }[] = [];
  errorMessage: string = '';

  ngAfterViewChecked() {
  this.scrollToBottom();
  }

  constructor(private http: HttpClient, location: Location) {
    super(location); // call the constructor of the base class
  }

  onQuestionnaireDone() {
    this.questionnaireDone = true;
  }




  sendMessage() {
    // prevent sending if empty message or already waiting
    if (!this.userMessage.trim() || this.isWaitingForBot) return;

    const userMessage = this.userMessage;
    this.isWaitingForBot = true; // lock sending

    // immediately push the user msg with placeholder bot reply
    this.chatHistory.push(
      this.botRepliesEnabled
        ? { user: userMessage, bot: '' }
        : { user: userMessage }
    );


    this.userMessage = '';


  // always build payload
  const payload: any = {
    message: userMessage,
    bot_enabled: this.botRepliesEnabled
  };
  if (this.entryId) {
    payload.entry_id = this.entryId;
  }


  if (!this.botRepliesEnabled) {
    // still call backend, but no bot reply
    this.http.post<{ entry_id: number }>(
      'http://127.0.0.1:8000/chat',
      payload
    ).subscribe({
      next: (res) => {
        if (!this.entryId) {
          this.entryId = res.entry_id; // get entry_id from first msg
          //this.entryId = this.entryId;
        }
        this.scrollToBottom();
      },
      error: (err) => {
        console.error('Chat error (bot disabled mode):', err);
        this.errorMessage = '⚠️ Failed to save entry.';
      },
      complete: () => {
        this.isWaitingForBot = false;
      }
    });
    return;
  }
  // -------------------bot mode enabled ------------------
    this.http.post<{ user: string, bot: string, entry_id: number }>(
      'http://127.0.0.1:8000/chat',
      payload
    ).subscribe({
      next: (res) => {
        // save entry_id from first response if not already set
        if (!this.entryId) {
          this.entryId = res.entry_id;
        }

        // update last message with bot reply
        const lastIndex = this.chatHistory.length - 1;
        this.chatHistory[lastIndex].bot = res.bot;
        this.scrollToBottom();
      },
      error: (err) => {
        const lastIndex = this.chatHistory.length - 1;  
        this.chatHistory[lastIndex].bot = 'Failed to contact the AI.';
        this.errorMessage = 'Failed to contact the AI. Please make sure the backend server is running.';
        
        console.error('Chat error:', err);
      },
      complete: () => {
        // unlock sending when finished (yes or error)
        this.isWaitingForBot = false;
      }
    });
  }


  scrollToBottom() {
    setTimeout(() => {
      if (this.messagesContainer && this.userAtBottom) {
        const el = this.messagesContainer.nativeElement;
        el.scrollTop = el.scrollHeight;
      }
    }, 0);
  }


  /**endEntry() {
      this.resetState();
      this.goBack();
  }**/

    // helper function to restet compoennt state
    private resetState() {
        this.chatHistory = [];
        this.entryId = undefined;
        this.userMessage = '';
        this.questionnaireDone = false; // reset the questionnaire state too
    }




//----------------------sentiment analysis----------------------

  async endEntry(entryId?: number) {
    const id = entryId ?? this.entryId;
    if (!id) {
      console.error("No valid entry_id to end session");
      return;
    }

    try {
      const userText = await this.fetchUserMessages(id);

      if (!userText.trim()) {
        console.error("No user messages found for analysis");
        return;
      }


      // 1) save analysis --> post to DB
      this.http.post("http://localhost:8000/analyze-all", { entry_id: id })
        .subscribe({
          next: (res: any) => console.log("Arousal/Valence analysis saved:", res),
          error: (err) => console.error("Analyze & save failed:", err)
        });

      this.resetState();
      this.goBack();

    } catch (err) {
      console.error("Failed to fetch messages for analysis:", err);
    }
  }

  private fetchUserMessages(entryId: number): Promise<string> {
    return this.http.get<{ history: { sender: string, content: string, timestamp: string }[] }>(
      `http://localhost:8000/history?entry_id=${entryId}`
    )
    .toPromise()
    .then(res => {
      if (!res || !res.history) return ''; // handle undefined

      // only user messages, concatenated into one text block
      return res.history
        .filter(msg => msg.sender === 'user')
        .map(msg => msg.content)
        .join('\n');
    });
  }


}
