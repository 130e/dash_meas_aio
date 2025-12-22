import json
from typing import Any, Dict, List


def _get_indentation_level(line: str) -> int:
    """Calculate indentation level (number of leading spaces/tabs)"""
    stripped = line.lstrip()
    if not stripped:
        return -1  # Empty line
    indent = len(line) - len(stripped)
    return indent // 2


def _parse_line(line: str) -> List[str]:
    """Parse the content of a line"""
    # Remove braces
    line = line.replace("{", "").replace("}", "")
    # Strip and remove trailing commas
    line = line.strip().rstrip(",")
    # colon values
    colon_splits = [v.strip() for v in line.split(":") if v.strip()]
    # At most two values, separated by one space
    values = []
    for part in colon_splits:
        values.extend(part.split(" ", 1))
    return values


def _cleanup_empty_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cleanup empty dictionaries from the nested dictionary.
    """
    is_list_key = False
    for k, v in d.items():
        if isinstance(v, dict) and len(v) == 0:
            is_list_key = True
            break
    if is_list_key:
        result = []
        for k, v in d.items():
            if len(v) == 0:
                result.append(k)
            else:
                result.append({k: _cleanup_empty_dict(v)})
        if len(result) == 1:
            result = result[0]
    else:
        result = {k: _cleanup_empty_dict(v) for k, v in d.items()}
    return result


def parse_asn1(lines: List[str]) -> tuple[dict[str, Any], int]:
    """
    Parse ASN.1 notation text and return a nested dictionary structure.
    """
    # Handle message root line
    values = []
    i = 0
    level = 0
    while i < len(lines) and len(values) == 0:
        line = lines[i].replace("::=", " ")
        values = _parse_line(line)
        level = _get_indentation_level(line)
        i += 1
    if len(values) == 2:
        root = {values[1]: {}}
    else:
        print(f"Invalid root line: {line}")
        return {}, 0

    # Parse lines and build tree
    stack = [(level, root)]
    while i < len(lines):
        line = lines[i]
        values = _parse_line(line)
        if not values:
            i += 1
            continue
        level = _get_indentation_level(line)
        while stack and stack[-1][0] >= level:
            stack.pop()
        if not stack:
            # print("Current packet ends while extra lines remain")
            break

        # Check if implicit nesting is needed
        while level - stack[-1][0] > 1:
            enumerate_key = chr(0x30 + len(stack[-1][1]))
            stack[-1][1][enumerate_key] = {}
            stack.append((stack[-1][0] + 1, stack[-1][1][enumerate_key]))
        for v in values:
            stack[-1][1][v] = {}
            stack.append((level, stack[-1][1][v]))
            level += 1
        i += 1

    return _cleanup_empty_dict(root), i


def parse_asn1_text(text: str) -> Dict[str, Any]:
    """
    Parse ASN.1 notation text and return a nested dictionary structure.
    """
    lines = text.splitlines()
    return parse_asn1(lines)


def locate_pair(root: Dict[str, Any], key: str, value: str) -> List[str]:
    """
    Find a key value pair in the nested dictionary.
    """
    for k, v in root.items():
        if k == key:
            if v == value:
                return [k]
            else:
                return [k] + locate_pair(v, key, value)
    return []


if __name__ == "__main__":
    print("Showing Demo...")

    sample1 = """
    value PCCH-Message ::= 
    {
      message c1 : paging : 
          {
            pagingRecordList 
            {
              {
                ue-Identity s-TMSI : 
                  {
                    mmec '00101010'B,
                    m-TMSI '11110000 11010000 00110011 00011110'B
                  },
                cn-Domain ps
              }
            }
          }
    }
    """

    sample2 = """
    value DL-DCCH-Message ::= 
    {
      message c1 : rrcConnectionReconfiguration : 
          {
            rrc-TransactionIdentifier 1,
            criticalExtensions c1 : rrcConnectionReconfiguration-r8 : 
                {
                  measConfig 
                  {
                    measObjectToRemoveList 
                    {
                      3
                    },
                    measObjectToAddModList 
                    {
                      {
                        measObjectId 6,
                        measObject measObjectEUTRA : 
                          {
                            carrierFreq 5230,
                            allowedMeasBandwidth mbw50,
                            presenceAntennaPort1 TRUE,
                            neighCellConfig '10'B,
                            cellsToAddModList 
                            {
                              {
                                cellIndex 1,
                                physCellId 171,
                                cellIndividualOffset dB2
                              }
                            },
                            measCycleSCell-r10 sf160
                          }
                      }
                    },
                    measIdToRemoveList 
                    {
                      4
                    },
                    measIdToAddModList 
                    {
                      {
                        measId 7,
                        measObjectId 6,
                        reportConfigId 3
                      }
                    }
                  },
                  radioResourceConfigDedicated 
                  {
                    mac-MainConfig explicitValue : 
                      {
                        timeAlignmentTimerDedicated infinity,
                        mac-MainConfig-v1020 
                        {
                        }
                      },
                    physicalConfigDedicated 
                    {
                      cqi-ReportConfig-r10 
                      {
                        cqi-ReportAperiodic-r10 setup : 
                          {
                            cqi-ReportModeAperiodic-r10 rm31,
                            aperiodicCSI-Trigger-r10 
                            {
                              trigger1-r10 '01100000'B,
                              trigger2-r10 '00011000'B
                            }
                          },
                        nomPDSCH-RS-EPRE-Offset 0,
                        cqi-ReportPeriodic-r10 setup : 
                          {
                            cqi-PUCCH-ResourceIndex-r10 18,
                            cqi-pmi-ConfigIndex 130,
                            cqi-FormatIndicatorPeriodic-r10 widebandCQI-r10 : 
                              {
                              },
                            ri-ConfigIndex 322,
                            simultaneousAckNackAndCQI FALSE
                          }
                      },
                      pucch-ConfigDedicated-v1020 
                      {
                        pucch-Format-r10 format3-r10 : 
                          {
                            n3PUCCH-AN-List-r13 
                            {
                              0,
                              1,
                              2,
                              3
                            }
                          }
                      }
                    }
                  },
                  nonCriticalExtension 
                  {
                    lateNonCriticalExtension 
                      CONTAINING
                      {
                        nonCriticalExtension 
                        {
                          antennaInfoDedicatedPCell-v10i0 
                          {
                            maxLayersMIMO-r10 fourLayers
                          }
                        }
                      },
                    nonCriticalExtension 
                    {
                      nonCriticalExtension 
                      {
                        sCellToReleaseList-r10 
                        {
                          2
                        },
                        sCellToAddModList-r10 
                        {
                          {
                            sCellIndex-r10 4,
                            antennaInfoDedicatedSCell-v10i0 
                            {
                              maxLayersMIMO-r10 fourLayers
                            }
                          },
                          {
                            sCellIndex-r10 2,
                            cellIdentification-r10 
                            {
                              physCellId-r10 171,
                              dl-CarrierFreq-r10 5230
                            },
                            radioResourceConfigCommonSCell-r10 
                            {
                              nonUL-Configuration-r10 
                              {
                                dl-Bandwidth-r10 n50,
                                antennaInfoCommon-r10 
                                {
                                  antennaPortsCount an4
                                },
                                phich-Config-r10 
                                {
                                  phich-Duration normal,
                                  phich-Resource one
                                },
                                pdsch-ConfigCommon-r10 
                                {
                                  referenceSignalPower 21,
                                  p-b 1
                                }
                              }
                            },
                            radioResourceConfigDedicatedSCell-r10 
                            {
                              physicalConfigDedicatedSCell-r10 
                              {
                                nonUL-Configuration-r10 
                                {
                                  antennaInfo-r10 
                                  {
                                    transmissionMode-r10 tm4,
                                    codebookSubsetRestriction-r10 '00000000 00000000 00000000 00000000 11111111 11111111 11111111 11111111'B,
                                    ue-TransmitAntennaSelection release : NULL
                                  },
                                  pdsch-ConfigDedicated-r10 
                                  {
                                    p-a dB-3
                                  }
                                },
                                ul-Configuration-r10 
                                {
                                  cqi-ReportConfigSCell-r10 
                                  {
                                    cqi-ReportModeAperiodic-r10 rm31,
                                    nomPDSCH-RS-EPRE-Offset-r10 0
                                  }
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
          }
    }
    """

    print("\n=== Parsing Sample 1 ===")
    root1 = parse_asn1_text(sample1)
    print(json.dumps(root1, indent=2))

    print("\n=== Parsing Sample 2 ===")
    root2 = parse_asn1_text(sample2)
    print(json.dumps(root2, indent=2))
