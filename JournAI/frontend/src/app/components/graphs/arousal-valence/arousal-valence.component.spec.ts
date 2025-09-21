import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ArousalValenceComponent } from './arousal-valence.component';

describe('ArousalValenceComponent', () => {
  let component: ArousalValenceComponent;
  let fixture: ComponentFixture<ArousalValenceComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ArousalValenceComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(ArousalValenceComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
