import { Router } from '@angular/router';
import { Component, OnInit } from '@angular/core';
import { MatToolbarModule } from '@angular/material/toolbar';
import { Location, CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { BaseComponent } from '../base/base.component';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    MatToolbarModule,
    CommonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    FormsModule,
    MatButtonModule
  ],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss'
})
export class SettingsComponent extends BaseComponent implements OnInit {
  userData = {
    name: '',
    age: null as number | null,
    gender: ''
  };

  showConfirmDialog = false;


  constructor(location: Location, private http: HttpClient, private router: Router) {
    super(location);
  }

  ngOnInit(): void {
    this.loadUserData();
  }

  loadUserData() {
    this.http.get<any>('http://localhost:8000/UserExists').subscribe(res => {
      if (res.userExists) {
        this.http.get<any>('http://localhost:8000/UserData').subscribe(data => {
          this.userData.name = data.name || '';
          this.userData.age = data.age;
          this.userData.gender = data.gender;
        });
      }
    });
  }

  modifyUser() {
    // this could toggle UI state if needed
  }

  saveUser() {
    if (!this.userData.age || !this.userData.gender) return;
    this.http.post('http://localhost:8000/User', {
      name: this.userData.name || null,
      age: this.userData.age,
      gender: this.userData.gender
    }).subscribe(() => {
      // optionally show feedback
    });
  }


deleteAllData() {
  this.showConfirmDialog = true;
}

confirmDelete() {
    this.http.delete('http://localhost:8000/DeleteAllData', {}).subscribe(() => {
    alert('All data deleted');
    this.router.navigate(['/']);
  });
  this.showConfirmDialog = false;
}

cancelDelete() {
  this.showConfirmDialog = false;
}
}
