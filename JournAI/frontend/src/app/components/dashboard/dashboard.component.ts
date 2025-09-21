import { Component } from '@angular/core';
import {Router} from '@angular/router';
import { Location, CommonModule } from '@angular/common';
import {MatGridListModule} from '@angular/material/grid-list';
import {MatToolbarModule} from '@angular/material/toolbar';
import { MatIconModule } from '@angular/material/icon';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';


import { BaseComponent } from '../base/base.component';


import { GraphService } from '../graphs/graph.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [MatGridListModule, CommonModule, MatToolbarModule, FormsModule, MatIconModule ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent extends BaseComponent {
spiderAxes: any;
histogramAxes: any;
noteContent: string = '';
showDisclaimer: boolean = false;



  constructor(private router: Router,  location: Location, private http: HttpClient,public graphService: GraphService) {
    super(location); //call the constructor of the base class
  }

  ngOnInit() {
    this.http.get<any>('http://localhost:8000/note').subscribe(res => {
      this.noteContent = res.content || '';
    });
  }


  tiles= [
    {text: 'Journal', cols: 1, rows:1, clickable: true, route: '/journal'},
    {text: 'Past Entries', cols: 1, rows:1, clickable: true, route: '/entries'},
    {text: 'Add Metrics', cols:1 , rows:1, clickable: true, route: '/add-metric'},
    {text: 'Graphs', cols: 1, rows:1, clickable: true, route: '/graphs'}
  ]



  onTileClick(tile: any): void {
      this.router.navigate([tile.route]);
  }

  onSettingsClick(): void {
    this.router.navigate(['/settings']);
  }

  saveNote() {
    this.http.post('http://localhost:8000/note', {
      content: this.noteContent
    }).subscribe();
  }

    toggleDisclaimer() {
    this.showDisclaimer = !this.showDisclaimer;
  }
}
