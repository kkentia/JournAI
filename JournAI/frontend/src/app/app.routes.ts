import { Routes } from '@angular/router';
import { HomepageComponent } from './components/homepage/homepage.component';
import { JournalComponent } from './components/journal/journal.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { SettingsComponent } from './components/settings/settings.component';
import { PastEntriesComponent } from './components/past-entries/past-entries.component';
import { userSetupGuard } from './guards/route.guard';
import { ArousalValenceComponent } from './components/graphs/arousal-valence/arousal-valence.component';
import { AddMetricsComponent } from './components/add-metrics/add-metrics.component';
import { ThemeriverComponent } from './components/graphs/themeriver/themeriver.component';
import { GraphsComponent } from './components/graphs/graphs/graphs.component';



// HOW TO USE: path here is what we'll be using at the end of the url to access a different html page
// example: localhost:4200/journal

export const routes: Routes = [
  { path: '', component: HomepageComponent },
  {
    path: 'journal',
    component: JournalComponent,
    canActivate: [userSetupGuard],
  },
  {
    path: 'dashboard',
    component: DashboardComponent,
    canActivate: [userSetupGuard],
  },
  {
    path: 'settings',
    component: SettingsComponent,
    canActivate: [userSetupGuard],
  },
  {
    path: 'entries',
    component: PastEntriesComponent,
    canActivate: [userSetupGuard],
  },
  { path: 'arousal-valence',
    component: ArousalValenceComponent,
  canActivate: [userSetupGuard]
  },
  {path:'add-metric',
    component: AddMetricsComponent,
    canActivate: [userSetupGuard]
  },
  {path:'themeriver',
    component: ThemeriverComponent,
    canActivate: [userSetupGuard]
  },
  {path:'graphs',
    component:GraphsComponent,
    canActivate:[userSetupGuard]
  }
];
