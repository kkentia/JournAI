import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PlutchikWheelComponent } from './plutchik-graph.component';

describe('PlutchikGraphComponent', () => {
  let component: PlutchikWheelComponent;
  let fixture: ComponentFixture<PlutchikWheelComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PlutchikWheelComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(PlutchikWheelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
