import { GraphQLClient, gql } from 'graphql-request';

const NEXUS_API_URL = 'http://localhost:8000/graphql';

export const client = new GraphQLClient(NEXUS_API_URL);

export const CREATE_MISSION_INTENT_MUTATION = gql`
  mutation CreateMissionIntent($missionName: String!, $description: String!) {
    createMissionIntent(missionName: $missionName, description: $description) {
      id
      missionName
      description
      status
    }
  }
`;
