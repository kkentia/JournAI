import { ActivatedRoute, Router } from '@angular/router';
import { Component, OnInit} from '@angular/core';
import { MatToolbarRow, } from '@angular/material/toolbar';
import {MatGridListModule} from '@angular/material/grid-list';
import {MatToolbarModule} from '@angular/material/toolbar';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

import { GraphService, GraphView } from '../graph.service';
import { SpiderGraphComponent } from '../spider-graph/spider-graph.component';
import { HistogramComponent } from "../histogram/histogram/histogram.component";
import { ArousalValenceComponent } from '../arousal-valence/arousal-valence.component';
import { PlutchikWheelComponent } from '../plutchik-graph/plutchik-graph.component';
import { ThemeriverComponent } from '../themeriver/themeriver.component';
@Component({
  selector: 'app-graphs',
  standalone: true,
  imports: [CommonModule,MatToolbarRow,FormsModule,MatToolbarModule,MatGridListModule,SpiderGraphComponent,HistogramComponent,ArousalValenceComponent,PlutchikWheelComponent,ThemeriverComponent],
  templateUrl: './graphs.component.html',
  styleUrl: './graphs.component.scss'
})
export class GraphsComponent implements OnInit{

  focusedGraph: 'spider' | 'plutchik' | 'va' | 'themeriver' | 'hist' | null = null;
  graphsVisible = false;
  currentView: GraphView = this.graphService.getCurrentView();

  popupVisible = false;

  constructor(private route: ActivatedRoute, private router: Router, private graphService: GraphService) {}


  ngOnInit() {
    //listens for changes in the urls parameters
    this.route.queryParamMap.subscribe(params => {
      const entryId = params.get('entry_id');
      const sessionId = params.get('session_id');

      this.graphService.setFilter({
        entryId: entryId ? Number(entryId) : undefined,
        sessionId: sessionId ? Number(sessionId) : undefined
      });
    });

      this.graphService.selectedView$.subscribe(view => {
      this.currentView = view;
    });
  }

  setView(view: GraphView) {
    this.graphService.setView(view);
    this.router.navigate(['/graphs'])
    this.currentView = view;
  }

  focus(graph: 'spider' | 'plutchik' | 'va' | 'themeriver' | 'hist') { this.focusedGraph = graph; }
  exitFocus() { this.focusedGraph = null; }
  closeGraph() { this.router.navigate(['/dashboard']); }

}