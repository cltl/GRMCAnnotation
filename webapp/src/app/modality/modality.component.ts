import {Component, Input, OnInit} from '@angular/core';
import {Scenario, Signal} from "../scenario";
import {ScenarioService} from "../scenario.service";
import {Options} from "@angular-slider/ngx-slider";
import {le as lowerBound} from "binary-search-bounds";


function compareByTimestamp(a: Signal, b: Signal): number {
  if (a.time && b.time) {
    return a.time.start - b.time.start;
  }

  return a.time ? 1 : -1;
}

@Component({
  selector: 'app-modality',
  templateUrl: './modality.component.html',
  styleUrls: ['./modality.component.css']
})
export class ModalityComponent implements OnInit {
  @Input() scenario: Scenario;
  @Input() modality: string;

  sliderOptions: Options = {
    floor: 0,
    ceil: 1,
    showTicks: true,
  };

  rangeOptions: Options = {
    floor: 0,
    ceil: 1,
    draggableRange: true,
    pushRange: true,
    readOnly: true
  };

  signals: Signal[];
  signalEntries: Array<[number, Signal]>;
  selectedSignal: number = 0;

  constructor(private scenarioService: ScenarioService) { }

  ngOnInit(): void {
    this.loadSignals(this.modality);
  }

  loadSignals(modality: string): void {
    this.scenarioService.loadSignals(modality)
      .subscribe(signals => {
        this.signals = this.setDefaultTimes(signals.sort(compareByTimestamp));
        this.signalEntries = Array.from(this.signals.entries());
        this.setupSlider();
      });
  }

  setupSlider(): void {
    let timestamps = this.signals.map(signal => signal.time.start)

    let options = Object.assign({}, this.sliderOptions);
    options.floor = 0;
    options.ceil = this.signals.length - 1;
    options.customValueToPosition = (val: number, minVal: number, maxVal: number): number => {
        return this.indexToTimlinePercentage(val, this.scenario, this.signals);
      };
    options.customPositionToValue = (percent: number, minVal: number, maxVal: number): number => {
        return this.timelinePercentageToIndex(percent, maxVal, minVal, this.scenario, timestamps);
      };

    this.selectedSignal = 0;
    this.sliderOptions = options;

    let rangeOptions = Object.assign({}, this.rangeOptions);
    rangeOptions.floor = this.scenario.start;
    rangeOptions.ceil = this.scenario.end;

    this.rangeOptions = rangeOptions;
  }

  private timelinePercentageToIndex(percent: number, maxVal: number, minVal: number, scenario: Scenario, timestamps: number[]) {
    let time: number = percent * (scenario.end - scenario.start) + scenario.start;
    let lowerIdx = lowerBound(timestamps, time);

    if (lowerIdx === timestamps.length - 1) {
      return timestamps.length - 1;
    }

    return time - timestamps[lowerIdx] <= timestamps[lowerIdx + 1] - time ? lowerIdx : lowerIdx + 1;
  }

  private indexToTimlinePercentage(val: number, scenario: Scenario, signals: Signal[]) {
    return (signals[val].time.start - scenario.start)/(scenario.end -scenario.start);
  }

  setDefaultTimes(signals: Signal[]) {
    let noTimestampsPresent = signals.every(signal => !signal.time);
    if (noTimestampsPresent) {
      let equalSpacing = signals.length > 1 ?
        (this.scenario.start - this.scenario.end)/(signals.length - 1) : 0;

      return signals.map((signal, idx) => {
        signal.time = {start: idx * equalSpacing, end: idx * equalSpacing + 1};
        return signal;
      });
    }

    return signals.map((signal, idx) => {
      signal.time = signal.time || {start: 0, end: 0};
      return signal;
    });
  }

  onSignalSelect(idx: number): void {
    this.selectedSignal = idx;
  }
}