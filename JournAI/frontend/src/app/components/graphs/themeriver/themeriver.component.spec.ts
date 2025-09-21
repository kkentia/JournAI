import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ThemeriverComponent } from './themeriver.component';

describe('ThemeriverComponent', () => {
  let component: ThemeriverComponent;
  let fixture: ComponentFixture<ThemeriverComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ThemeriverComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(ThemeriverComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
