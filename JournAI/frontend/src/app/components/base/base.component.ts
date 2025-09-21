import { Component } from '@angular/core';
import { Location } from '@angular/common';

@Component({
  selector: 'app-base',
  standalone: true,
  imports: [],
  templateUrl: './base.component.html',
  styleUrl: './base.component.scss'
})
export class BaseComponent {
  constructor(protected location: Location) {}

  goBack() {
    this.location.back();
  }
}
