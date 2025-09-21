import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import {FormsModule} from '@angular/forms'; // we need it so that ngSubmit can work
import { CommonModule } from '@angular/common';
import {HttpClient} from '@angular/common/http';


@Component({
  selector: 'app-homepage',
  standalone: true,
  imports: [FormsModule, CommonModule],
  templateUrl: './homepage.component.html',
  styleUrl: './homepage.component.scss'
})
export class HomepageComponent implements OnInit {
  age:number | null = null;
  gender: string = 'other';
  constructor(private router: Router, private http:HttpClient) { }

  ngOnInit(): void {
    this.checkUserExists();  }

  checkUserExists() {
    this.http.get('http://localhost:8000/UserExists').subscribe({
      next: (exists: any) => {
        if (exists && exists.userExists) {
          this.router.navigate(['/dashboard']);
        }
      },
      error: (err) => console.error('Error checking user existence:', err)
    });
  }



  onSubmit() {
    if (this.age !== null && this.age > 0 && this.age <= 100) {
      this.http.post('http://localhost:8000/User', {
        age: this.age,
        gender: this.gender
      }).subscribe({
        next: () => this.router.navigate(['/dashboard']),
        error: (err) => console.error('Failed to submit user data:', err)
      });
    }
  }

}
