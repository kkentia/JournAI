import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SpiderGraphComponent } from './spider-graph.component';

describe('SpiderGraphComponent', () => {
  let component: SpiderGraphComponent;
  let fixture: ComponentFixture<SpiderGraphComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SpiderGraphComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(SpiderGraphComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
